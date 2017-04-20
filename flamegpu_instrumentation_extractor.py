""" Python script to process the output of a set of batch jobs, extracting key information to dump to csv
@author Peter Heywood <p.heywood@sheffield.ac.uk>

"""

import argparse
import re
import os
import sys
import csv
import math
import datetime
import subprocess
import pathlib
from distutils.util import strtobool
from collections import OrderedDict


def user_yes_no_query(question):
    # http://stackoverflow.com/questions/3041986/python-command-line-yes-no-input
    sys.stdout.write('%s [y/n]\n' % question)
    while True:
        try:
            return strtobool(input().lower())
        except ValueError:
            sys.stdout.write('Please respond with \'y\' or \'n\'.\n')

def create_directory(directory):
    if not os.path.isdir(directory):
        try:
            os.makedirs(directory)
        except OSError as exception:
            if exception.errno != errno.EEXIST:
                print("ERROR: Directory `{:}` could not be created. Aborting.".format(directory))
                return False
    return True

class InstrumentationExtractor:


    def __init__(self, args):
        # Set defaults
        self.verbose = False
        self.force = False
        self.pretty = False
        self.input = []
        self.output = None

        # Parse input arguments
        self.process_flags(args)
        self.process_args(args)

        # Prepare other class variables
        self.input_files = []
        self.data = OrderedDict()

        # Validate
        self.validate()

    def process_flags(self, args):
        if "verbose" in args:
            self.verbose = args["verbose"]
        if "force" in args:
            self.force = args["force"]
        if "pretty" in args:
            self.pretty = args["pretty"]

    def process_args(self, args):
        if "input" in args and args["input"] is not None:
            self.input = args["input"]
        if "output" in args and args["output"] is not None and len(args["output"]) > 0:
            self.output = args["output"][0]

    def get_num_input_files(self):
        return len(self.input_files)

    def validate(self):
        # For each input argument ensure it exists. If it does not issue a warning and remove it.
        for i in self.input:
            if os.path.exists(i):
                # If it is a directory, find all its children, add them to the list of files to parse.
                if os.path.isdir(i):
                    for root, subdirs, files in os.walk(i):
                        for file in files:
                            self.input_files.append(os.path.join(root, file))
                    pass
                # Otherwise if it is a file add it to the files list.
                elif os.path.isfile(i):
                    self.input_files.append(i)
            else:
                print("WARNING: Input argument {:} is not a valid file or directory. Ignoring.".format(i))

        # Create the output directory if it does not exist, if there is valid input file(s)
        if len(self.input_files) > 0:
            create_directory(self.output)


    def parse_results(self):
        self.data = []
        print("Processing {:} input files".format(self.get_num_input_files()))
        # For each input file
        file_counter = 1
        num_files = self.get_num_input_files()
        for input_file in self.input_files:
            # print("Processing file {:} of {:}".format(file_counter, num_files))
            file_data = self.parse_file(input_file)
            if file_data is not None:
                self.data.append(file_data)
            file_counter += 1

    def parse_file(self, input_file):
        is_flamegpu_file = False
        # Prepare dict to represent file data
        data = OrderedDict()
        data["input_file"] = input_file
        # Open the file
        with open(input_file, "r") as f:
            for line in f:
                line = line.rstrip()
                if line.startswith("FLAMEGPU Console mode"):
                    is_flamegpu_file = True
                if line.startswith("Initial states: "):
                    data["initial_states"] = line.replace("Initial states: ", "")
                elif line.startswith("Output dir: "):
                    data["output_dir"] = line.replace("Output dir: ", "")
                elif line.startswith("Device "):
                    data["device_string"] = line.replace("Device ", "")
                elif line.startswith("Total Processing time: "):
                    data["total_processing_time"] = line.replace("Total Processing time: ", "").replace(" (ms)", "")

                if "instrumentation" not in data:
                    data["instrumentation"] = OrderedDict()
                if "population" not in data:
                    data["population"] = OrderedDict()
                if line.startswith("Instrumentation: "):
                    # Strip out unneccesary info
                    string = line.replace("Instrumentation: ", "").replace(" (ms)", "")
                    # Split on the equals symbol
                    split_string = string.split(" = ")
                    if len(split_string) == 2:
                        k, v = split_string
                        # If the key is not in the insrumentation data, add it.
                        if k not in data["instrumentation"]:
                            data["instrumentation"][k] = []
                        data["instrumentation"][k].append(float(v))
                if line.startswith("agent_") and "_count:" in line:
                    split_line  = line.split(": ")
                    agent_type_state = split_line[0].replace("agent_", "").replace("_count", "")
                    count = int(split_line[-1])
                    if agent_type_state not in data["population"]:
                        data["population"][agent_type_state] = []
                    data["population"][agent_type_state] = count

        if is_flamegpu_file:
            return data
        else:
            print("ERROR: File {:} is not flamegpu output".format(input_file))
            return None


    def output_data(self):
        if self.output is not None:
            self.output_data_csv()
        else:
            print("Error: No output file specified")


    def output_data_csv(self):
        # Attempt to open the output file
        success = True
        for i, file_data in enumerate(self.data):
            csv_data = []
            fname = "{:}__{:}.csv".format(i, os.path.split(file_data["input_file"])[-1])
            output_file = os.path.normpath(os.path.join(self.output, fname))
            if os.path.isfile(output_file) and not self.force:
                if not user_yes_no_query("Do you wish to overwrite output file {:}".format(output_file)):
                    success = False
                    continue
            try:
                with open(output_file, 'w', newline='') as f:
                    # Prepare data as csv
                    fieldnames = [
                        "filename",
                        "total processing time (ms)",
                        "iteration"
                    ]

                    for agent_type_state in file_data["population"]:
                        fieldnames.append(agent_type_state)

                    for fn in file_data["instrumentation"]:
                        fieldnames.append(fn + " (ms)")
                
                    num_iterations = max([len(file_data["instrumentation"][d]) for d in file_data["instrumentation"]])
                    for iteration in range(num_iterations):
                        row = []
                        row.append(file_data["input_file"])
                        row.append(file_data["total_processing_time"])
                        row.append(iteration)
                        for agent_type_state in file_data["population"]:
                            pop = file_data["population"][agent_type_state]
                            row.append(pop)
                        for fn in file_data["instrumentation"]:
                            millis = None
                            if iteration  < len(file_data["instrumentation"][fn]):
                                millis = file_data["instrumentation"][fn][iteration]
                            row.append(millis)
                        csv_data.append(row)

                    # Write the data out as a csv file.
                    writer = csv.writer(f, delimiter=",")
                    if len(fieldnames) > 0:
                        writer.writerow(fieldnames)
                    for row in csv_data:
                        writer.writerow(row)
                    success = True
            except Exception as exception:
                print("ERROR: File `{:}` could not be opened for writing.".format(output_file))
                success =  False
        return success

def main():
    parser = argparse.ArgumentParser(
        description="Result extractor for benchmarks."
    )

    parser.add_argument(
        "-i",
        "--input",
        type=str,
        nargs="+",
        help="Input files or directories to parse.",
        required=True
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        nargs=1,
        help="Directory for Output, produces one csv file per input file.",
        required=True
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="increase verbosity of output"
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force overwriting of files"
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Produce pretty-printed output (newlines)"
    )
    args = parser.parse_args()


    parser = InstrumentationExtractor(vars(args))
    parser.parse_results()
    parser.output_data()



if __name__ == "__main__":
    main()
