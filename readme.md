# FLAME GPU Instrumentation Extractor

This tool can be used to extract the instrumentation values from a FLAME GPU output log into a CSV.

## Usage 

Simple usage is as follows:

    python flamegpu_instrumentation_extractor.py -i /path/to/input/file  -o /path/to/output/directory 

Additional information can be found using the `-h` or `--help` options.

A single line is produced for each iteration in the log file, with an entry for the relevant instrumented lines.
