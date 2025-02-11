#!/usr/bin/env python3
"""Extract sample data of specified patients (from LocalApp or TSOPPI output directories)."""
import argparse
from datetime import datetime
import glob
import logging
from pathlib import Path
import re
import resources.software.TSOPPI_shared_functions as TSF
from typing import Dict, List, Pattern, Tuple
import subprocess
import sys

# Daniel Vodak
# Possible future work:
# - [?] TSOPPI: export variant summary files as well
#   - only if there was at least one exported patient dir. [reduce the summary file to export-eligible patients]
#   - add an option for variant summary file path regex
# - [?] TSOPPI: check for error messages
#   - actual errors vs. messages printed to stderr files
# - [?] check LoalApp and TSOPPI version (exit when non-supported versions are encountered)
# - [?] LocalApp: add an option to skip fastq files?
#   - [!] RNA samples have multiple, with the complete ones being unavailable in the output at analysis start from FASTQ files
# - load InPreD nomenclature regex string from an external config file
# - [!] enable correct identification of non-csv sample sheets supplied to the LocalApp
# - [!] re-write the log file instead of appending to it (a Python issue?!)


def reclassify_matching_paths(path_pattern: Pattern, path_dict: Dict[str: str], base_path: str) -> int:
    """Assign class "E" to paths from path_dict if they match given path_pattern. Return the number of matches."""

    # find all matching paths
    matching_paths = [file_path for file_path in path_dict if (re.fullmatch(path_pattern, file_path) is not None)]
    for available_path in matching_paths:
        path_dict[available_path] = "E"

        # mark directories on the path to the matching files as "I" (Ignore)
        parent_path = str(Path(available_path).parents[0])
        while (parent_path != base_path):
            if (parent_path in path_dict):
                path_dict[parent_path] = "I"
                parent_path = str(Path(parent_path).parents[0])
            else:
                break

    return(len(matching_paths))

def main():
    version_string = TSF.get_SADET_version()
    tool_tag = "TSOPPI_SADET"

    arg_parser = argparse.ArgumentParser(
        description="Extract data of specified patients (from LocalApp of TSOPPI output).")

    arg_parser.add_argument("--version", action="version",
                            version="%(prog)s " + version_string)

    # [required]
    arg_parser.add_argument("--input_data_directory", required=True,
                            help="Absolute path to a LocalApp or TSOPPI output directory (from which data should be extracted).")
    arg_parser.add_argument("--gpg_password_file", required=True,
                            help="Absolute path to a text file specifying a password that should be utilized for encryption"
                                " of the extracted data. The file should not contain anything except for the password on the first line."
                                " At least 16 characters (including a number, a small letter, a capital letter and an underscore) are recommended."
                                " Whitespace characters are not allowed.")
    arg_parser.add_argument("--sample_ID_list", required=True,
                            help="Absolute path to a text file specifying IDs of samples whose data should be extracted."
                                " A two-column tab-seperated file is expected, with the ID strings being listed in the second column."
                                " The first column should be used to specify an ID-matching method to be used with given ID (e.g., \"prefix\").")
    arg_parser.add_argument("--output_directory", required=True,
                            help="Absolute path to the directory in which all of the output files should be stored."
                                " If not existing, the directory will be created.")
    arg_parser.add_argument("--input_type", required=True,
                            choices=["LocalApp", "TSOPPI"],
                            default="LocalApp",
                            help="Type of TSO500 solid results that should serve as input for data extraction. (default value: %(default)s)")
    arg_parser.add_argument("--host_system_mounting_directory",
                            required=True,
                            help="Absolute path to the host system mounting"
                                " directory. The specified directory should"
                                " include all input and output file paths"
                                " in its directory tree.")
    # [optional]
    arg_parser.add_argument("--output_file_prefix",
                            help="Prefix used for all output files. If not set, a time-stamp based prefix will be generated."
                                " A prefix based on sequencing run ID is recommended."
                                " Note: Only alphanumeric characters and underscores are allowed.")
    arg_parser.add_argument("--generate_export_script_only",
                            action="store_true",
                            help="Only generate a script for the required data export (encryption and packaging),"
                                " do not run the script. (disabled by default)")
    arg_parser.add_argument("--parallel_export_and_md5sum",
                            action="store_true",
                            help="Run gpg/tar and md5sum in parallel. (disabled by default)")    
    arg_parser.add_argument("--require_inpred_nomenclature",
                            action="store_true",
                            help="Require that all input IDs are compatible with the InPreD sample nomenclature. (disabled by default)")
    arg_parser.add_argument("--archive_level_md5sum",
                            action="store_true",
                            help="Whether the md5sum should be created on the final tar.gpg archive instead of being creating on individual files. (disabled by default)")                          
    arg_parser.add_argument("--rewrite_output",
                            action="store_true",
                            help="Allow rewriting already existing output files. (disabled by default)")
    arg_parser.add_argument("--container_mounting_directory",
                            required=False, default="/inpred/data",
                            help="Container's inner mounting point."
                                " The host system mounting directory path/prefix"
                                " will be replaced by the container mounting"
                                " directory path in all input and output file"
                                " paths"
                                " (this parameter shouldn't be changed during regular use). (default value: %(default)s)")

    # parsing the supplied command-line arguments
    arg_dict = vars(arg_parser.parse_args())

    base_dir_path = arg_dict["container_mounting_directory"]
    host_system_prefix = arg_dict["host_system_mounting_directory"]
    output_dir_hs_path = arg_dict["output_directory"]
    input_dir_hs_path = arg_dict["input_data_directory"]
    pass_file_hs_path = arg_dict["gpg_password_file"]
    id_file_hs_path = arg_dict["sample_ID_list"]
    output_file_prefix = arg_dict["output_file_prefix"]
    input_type = arg_dict["input_type"]
    generate_export_script_only = arg_dict["generate_export_script_only"]
    parallel_export_and_md5sum = arg_dict["parallel_export_and_md5sum"]
    require_inpred_nomenclature = arg_dict["require_inpred_nomenclature"]
    archive_level_md5sum = arg_dict["archive_level_md5sum"]
    rewrite_output = arg_dict["rewrite_output"]
    #variant_summary_file_pattern = arg_dict["variant_summary_file_pattern"]

    # set up logging
    sadet_logger = logging.getLogger()
    sadet_logger.setLevel(logging.INFO)

    logging_formatter = logging.Formatter(fmt = "%(asctime)s [" + tool_tag + " - %(levelname)s] %(message)s", datefmt = "%Y-%m-%d_%H:%M:%S")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(logging_formatter)
    sadet_logger.addHandler(stdout_handler)

    # if no output file prefix is set by the user, set a date-based one
    if output_file_prefix is None:
        output_file_prefix = datetime.now().strftime("%Y_%m_%d___%H_%M_%S")

    # exit if user-supplied output file prefix contains anything but the allowed characters
    else:
        allowed_char_regex = re.compile("[a-zA-Z0-9_]+")
        prefix_forbidden_char_tail = re.sub(allowed_char_regex, "", output_file_prefix)
        if (len(prefix_forbidden_char_tail) > 0):
            logging.error("The supplied output file prefix contains forbidden characters (\""
                        + prefix_forbidden_char_tail[0] + "\")."
                        " Please refer to the help message for more information. Exiting.\n")
            exit(1)

    # conversion of input/output file and directory paths (host system -> container)
    # - output directory path
    (hs_prefix_present,
    output_dir_cont_path) = TSF.convert_path(output_dir_hs_path,
                                            host_system_prefix,
                                            base_dir_path)
    if not hs_prefix_present:
        logging.error(TSF.get_path_prefix_error_message("output directory",
                                                    output_dir_hs_path, host_system_prefix))
        exit(2)
    if not Path(output_dir_cont_path).is_dir():
        logging.info("The specified output results directory couldn't be located"
                    " within the container (path \"" + output_dir_cont_path
                    + "\"). Attempting to create it..")
        try:
            Path(output_dir_cont_path).mkdir(parents=False)
        except FileNotFoundError as fnf_error:
            logging.error("Could not create the output directory."
                        " Please make sure that its parent directory already"
                        " exists. Exiting after the original error message: "
                        + "\"" + repr(fnf_error) + "\"\n")
            exit(3)
        logging.info("Output directory created.")

    # - password file path
    (hs_prefix_present,
    pass_file_cont_path) = TSF.convert_path(pass_file_hs_path,
                                            host_system_prefix,
                                            base_dir_path)
    if not hs_prefix_present:
        logging.error(TSF.get_path_prefix_error_message("GPG password file",
                                                    pass_file_hs_path, host_system_prefix))
        exit(4)
    if not Path(pass_file_cont_path).is_file():
        logging.error(TSF.get_file_not_found_error_message("GPG password file",
                                                        pass_file_cont_path))
        exit(5)

    # - patient/sample ID file path
    (hs_prefix_present,
    id_file_cont_path) = TSF.convert_path(id_file_hs_path,
                                        host_system_prefix,
                                        base_dir_path)
    if not hs_prefix_present:
        logging.error(TSF.get_path_prefix_error_message("sample ID file",
                                                    id_file_hs_path, host_system_prefix))
        exit(6)
    if not Path(id_file_cont_path).is_file():
        logging.error(TSF.get_file_not_found_error_message("sample ID file",
                                                        id_file_cont_path))
        exit(7)

    # - input directory path
    (hs_prefix_present,
    input_dir_cont_path) = TSF.convert_path(input_dir_hs_path,
                                            host_system_prefix,
                                            base_dir_path)
    if not hs_prefix_present:
        logging.error(TSF.get_path_prefix_error_message("input directory",
                                                    input_dir_hs_path, host_system_prefix))
        exit(8)
    if not Path(input_dir_cont_path).is_dir():
        logging.error("The specified input data directory couldn't be located"
                    " (host system path: \"" + input_dir_hs_path
                    + "\"). Exiting.")
        exit(9)

    # determine the output file paths
    # - for runtime packaging
    outfile_password_path = pass_file_cont_path
    outfile_dir_parent_path = str(Path(input_dir_cont_path).parents[0])
    outfile_script_suffix = "_" + input_type + "_container_export.sh"
    outfile_script_stdout_log_path = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_container_export_stdout.log"
    outfile_script_stderr_log_path = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_container_export_stderr.log"
    outfile_file_path_list = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_files_to_export.txt"
    outfile_archive_path = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + ".tar.gpg"
    outfile_file_level_md5_path = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_individual_files.md5"
    outfile_archive_level_md5_path = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + ".tar.gpg.md5"
    # - for host-system packaging done later
    if generate_export_script_only:
        outfile_password_path = pass_file_hs_path
        outfile_dir_parent_path = str(Path(input_dir_hs_path).parents[0])
        outfile_script_suffix = "_" + input_type + "_host_system_export.sh"
        outfile_script_stdout_log_path = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + "_host_system_export_stdout.log"
        outfile_script_stderr_log_path = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + "_host_system_export_stderr.log"
        outfile_file_path_list = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + "_files_to_export.txt"
        outfile_archive_path = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + ".tar.gpg"
        outfile_file_level_md5_path = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + "_individual_files.md5"
        outfile_archive_level_md5_path = output_dir_hs_path + "/" + output_file_prefix + "_" + input_type + ".tar.gpg.md5"

    outfile_dir_name = Path(input_dir_cont_path).name
    outfile_log_cont = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + ".log"
    outfile_file_path_list_cont = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_files_to_export.txt"
    skipped_file_path_list_cont = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_files_to_skip.txt"
    inherited_error_list_cont = output_dir_cont_path + "/" + output_file_prefix + "_" + input_type + "_inherited_errors.txt"
    outfile_script_path_cont = output_dir_cont_path + "/" + output_file_prefix + outfile_script_suffix

    # terminate if result-overwriting is not enabled and the key output files already exist
    if not rewrite_output:
        if ((Path(outfile_log_cont).exists())
            or (Path(outfile_file_path_list_cont).exists())
            or (Path(skipped_file_path_list_cont).exists())):
            logging.info("(Some of) the target output files already exist and output overwriting has been disabled. Exiting.")
            exit(0)

    # save a copy of log messages into a file
    file_handler = logging.FileHandler(outfile_log_cont, mode = "w")
    file_handler.setFormatter(logging_formatter)
    sadet_logger.addHandler(file_handler)

    # output parameter setting information
    logging.info("TSOPPI: SAmple Data Extraction Tool, version "
                + version_string)
    logging.info("""Input parameter settings:
        - input type: """ + input_type + """
        - output file prefix: """ + output_file_prefix + """
        - allow rewriting output: """ + str(rewrite_output) + """
        - create archive-level md5sum file: """ + str(archive_level_md5sum) + """
        - require InPreD sample ID nomenclature: """ + str(require_inpred_nomenclature) + """
        - skip extraction script execution: """ + str(generate_export_script_only) + """
        - run gpg/tar and md5sum in parallel: """ + str(parallel_export_and_md5sum) + """
        - output directory ([host system]/[container]): ["""
        + output_dir_hs_path + "]/["
        + output_dir_cont_path + "]" + """
        - input data directory ([host system]/[container]): ["""
        + input_dir_hs_path + "]/["
        + input_dir_cont_path + "]" + """
        - GPG password file ([host system]/[container]): ["""
        + pass_file_hs_path + "]/["
        + pass_file_cont_path + "]" + """
        - sample ID specification file ([host system]/[container]): ["""
        + id_file_hs_path + "]/["
        + id_file_cont_path + "]")
        
    # dictionary for keeping track of file paths and their status codes
    available_file_paths_dict = {}

    # load the supplied ID list
    logging.info("Loading the supplied IDs...")
    header_read = False
    id_list_fi = {"matching_method": -1, "target_ID": -1}
    ID_prefix_list = [] # a list of loaded ID prefixes

    with open(id_file_cont_path, "r") as id_infile:
        for line in id_infile:

            line_s = line.strip().split("\t")
            if (len(line_s) < 2):
                logging.error("All lines of the input ID list file should contain at least two fields/columns."
                              " The following line has fewer: \"" + line.strip() + "\". Exiting.")
                exit(10)

            if (not header_read):
                for column_id in id_list_fi:
                    if not (column_id in line_s):
                        logging.error("Couldn't find the required \""
                                      + column_id + "\" data field in the supplied ID list. Exiting.")
                        exit(18)
                    id_list_fi[column_id] = line_s.index(column_id)
                header_read = True
            else:
                matching_method = line_s[id_list_fi["matching_method"]]
                ID_string = line_s[id_list_fi["target_ID"]]

                if (not ID_string in ["", "."]):
                    if (matching_method == "prefix"):
                        ID_prefix_list.append(ID_string)
                    else:
                        logging.warning(" - Unsupported ID matching method keyword encountered"
                                        " (method keyword: \"" + matching_method + "\", ID: \"" + ID_string + "\"). The ID will be ignored.")
                elif(ID_string == ""):
                    logging.warning(" - Unsupported ID string (encountered ID value: \"" + ID_string + "\"). The ID will be ignored.")
    logging.info(" - ID loading done (" + str(len(ID_prefix_list)) + " IDs loaded).")

    # load the extraction path patterns
    extraction_path_patterns_file = "/inpred/resources/data/extraction_path_patterns.tsv"
    # path patterns for files that should be extracted, broken down into sub-categories
    extraction_patterns = {"general_all": {}, "general_bcl": {}, "sample_DNA": {}, "sample_RNA": {},
                           "sample_DNA_bcl": {}, "sample_RNA_bcl": {},
                           "T_general": {}, "T_any_DNA": {}, "T_DNA_tumor_plus": {},
                           "T_DNA_tumor": {}, "T_DNA_normal": {}, "T_RNA_tumor": {}, "T_DNA_tumor_RNA_tumor": {}}

    with open(extraction_path_patterns_file, "r") as epp_infile:
        for line in epp_infile:

            line_s = line.strip().split("\t")

            if (len(line_s) < 4):
                logging.error("Too few columns on the following extraction path pattern file line: \""
                            + line.strip() + "\". Exiting.")
                exit(11)

            required_input_type = line_s[0]
            min_file_count = int(line_s[1])
            pattern_category = line_s[2]
            path_pattern = line_s[3]

            if (pattern_category not in extraction_patterns):
                logging.error("Unknown pattern category on the following extraction path pattern file line: \""
                            + line.strip() + "\". Exiting.")
                exit(12)
            
            if (required_input_type == input_type):
                extraction_patterns[pattern_category][path_pattern] = min_file_count

    # process LocalApp data
    if (input_type == "LocalApp"):
        logging.info("Processing the specified LocalApp output directory...")
        logging.info("Checking the directory content...")

        # check for error messages present in the LocalApp output's log files
        LA_EC_script_path = "/inpred/resources/software/check_LocalApp_error_logs.sh"
        if (Path(input_dir_cont_path + "/Logs_Intermediates").exists()):
            error_check_output = subprocess.run(["bash", LA_EC_script_path, input_dir_cont_path], capture_output = True, text = True)
            ECO_stdout_line_list = error_check_output.stdout.split("\n")
            if (ECO_stdout_line_list == ['']):
                logging.info("Found zero error lines in the LocalApp logs.")
            else:
                logging.info("Found " + str(len(ECO_stdout_line_list)) + " error lines in the LocalApp logs." 
                            " A copy of the error lines will be written into the inherited errors output file.")
                with open(inherited_error_list_cont, "w") as iel_outfile:
                    for error_line in ECO_stdout_line_list:
                        iel_outfile.write(error_line + "\n")
        else:
            logging.error("Unable to find the \"Logs_Intermediates\" sub-directory. Exiting.")
            exit(21)

        # check that there is exactly one file matching the expected sample sheet file path
        LA_samplesheet_path = "/Logs_Intermediates/SamplesheetValidation/*_SampleSheet.csv"
        LA_samplesheet_list = glob.glob(input_dir_cont_path + LA_samplesheet_path)
        (e_code, e_message) = TSF.check_file_list_size(LA_samplesheet_list, "sample sheet", input_dir_hs_path + LA_samplesheet_path, 13)
        if (e_code != 0):
            logging.error(e_message)
            exit(e_code)
        else:
            logging.info(e_message)

        # check that there is exactly one file matching the expected top-level log file path
        LA_logfile_path = "/trusight-oncology-500-ruo_ruo-2.2.0.12*.log"
        LA_logfile_list = glob.glob(input_dir_cont_path + LA_logfile_path)
        (e_code, e_message) = TSF.check_file_list_size(LA_logfile_list, "log file", input_dir_hs_path + LA_logfile_path, 14)
        if (e_code != 0):
            logging.error(e_message)
            exit(e_code)
        else:
            logging.info(e_message)

        # process the sample sheet file
        data_tag = None
        data_section = False
        header_read = False
        sample_sheet_data_fi = {"Sample_Type": -1, "Sample_ID": -1, "Pair_ID": -1}  # indexes of fields valid for processing

        # dictionaries for DNA and RNA samples that qualify for extraction
        DNA_sample_list = {}
        RNA_sample_list = {}

        with open(LA_samplesheet_list[0], "r") as lass_infile:
            for line in lass_infile:

                line_s = line.strip().replace(",", "\t").split("\t")

                # if the data section header is encountered, enable the data section processing mode
                if (line_s[0] in ["[Data]", "[TSO500S_Data]"]):
                    data_tag = line_s[0]
                    data_section = True
                # skip non-informative lines
                elif (len(line_s[0]) == 0):
                    continue
                # disable the data section processing mode if a non-data section header is encountered
                elif (line_s[0][0] == "["):
                    data_section = False
                # process the data section header line
                elif ((data_section) and (not header_read)):
                    for column_id in sample_sheet_data_fi:
                        if not (column_id in line_s):
                            logging.error("Couldn't find the required \""
                                        + column_id + "\" data field in the processed sample sheet file. Exiting.")
                            exit(15)
                        else:
                            sample_sheet_data_fi[column_id] = line_s.index(column_id)
                            #logging.info("\"" + column_id + "\" field index: " + str(line_s.index(column_id)) + ".")
                    header_read = True
                # process sample information
                elif ((data_section) and (header_read)):
                    sv_sample_type = line_s[sample_sheet_data_fi["Sample_Type"]]
                    sv_sample_id = line_s[sample_sheet_data_fi["Sample_ID"]]
                    sv_pair_id = line_s[sample_sheet_data_fi["Pair_ID"]]

                    # check whether the encountered sample IDs match any items on the input ID list
                    matching_ids = TSF.find_ID_match(sv_sample_id, ID_prefix_list, "prefix")
                    if (len(matching_ids) == 0):
                        logging.info("Skipping " + sv_sample_type + " sample \"" + sv_sample_id + "\" (no ID match).")
                    else:
                        # check compliance with the InPreD nomenclature, if enabled
                        if ((require_inpred_nomenclature) and (not TSF.is_InPreD_ID(sv_sample_id))):
                            logging.warning("The following sample ID doesn't comply with"
                                            " the InPreD ID nomenclature: \"" + ID_string + "\"). The sample will be ignored.")
                        else:
                            if (sv_sample_type == "DNA"):
                                DNA_sample_list[sv_sample_id] = {"pair_id": sv_pair_id, "pattern": matching_ids[0]}
                            elif (sv_sample_type == "RNA"):
                                RNA_sample_list[sv_sample_id] = {"pair_id": sv_pair_id, "pattern": matching_ids[0]}
                            else:
                                logging.error("Unknown sample type encountered (sample ID: \""
                                            + sv_sample_id + "\", sample type: \"" + sv_sample_type + "\"). Exiting.")
                                exit(16)

        # print summary information about the processed sample sheet
        if (data_tag is None):
            logging.error("Sample sheet version not identified, no sample information extracted. Exiting.")
            exit(17)
        elif ((len(DNA_sample_list) + len(RNA_sample_list)) == 0):
            logging.info("No samples suitable for extraction were identified within the processed sample sheet. Exiting.")
            exit(0)
        else:
            # sample sheet version info
            if (data_tag == "[Data]"): 
                logging.info("Sample sheet version v1 detected.")
            elif (data_tag == "[TSO500S_Data]"):
                logging.info("Sample sheet version v2 detected.")
            # DNA sample info
            logging.info(str(len(DNA_sample_list)) + " DNA samples with an ID match identified (sample ID [pair_ID] //matching_pattern):")
            for sample_id in DNA_sample_list:
                logging.info("  - \"" + sample_id + "\" [\"" + DNA_sample_list[sample_id]["pair_id"] + "\"] //\"" + DNA_sample_list[sample_id]["pattern"] + "\"")
            # RNA sample info
            logging.info(str(len(RNA_sample_list)) + " RNA samples with an ID match identified (sample ID [pair_ID] //matching_pattern):")
            for sample_id in RNA_sample_list:
                logging.info("  - \"" + sample_id + "\" [\"" + RNA_sample_list[sample_id]["pair_id"] + "\"] //\"" + RNA_sample_list[sample_id]["pattern"] + "\"")

        # determine whether the processed LocalApp output directory was generated from BCL files
        from_BCL = False
        with open(LA_logfile_list[0], "r") as lal_infile:
            for line in lal_infile:

                if ("stepName \"FastqGeneration\"" in line):
                    from_BCL = True
                    break
        if from_BCL:
            logging.info("Expecting output for a LocalApp analysis starting from BCL files.")
        else:
            logging.info("Expecting output for a LocalApp analysis starting from FASTQ files.")

        # load the paths of all files in the processed LocalApp output directory, set their default status to "S" (Skip)
        available_file_paths_dict = {item: "S" for item in glob.glob(input_dir_cont_path + "/**", recursive = True)}
        if ((input_dir_cont_path + "/") in available_file_paths_dict):
            del available_file_paths_dict[input_dir_cont_path + "/"]

        # go through the LocalApp path patterns for general files
        for file_pattern_type in ["general_all", "general_bcl"]:
            # if the LocalApp analysis was started from FASTQ files, skip looking for files generated from BCL input
            if ((file_pattern_type == "general_bcl") and (not from_BCL)):
                continue
            # check one path pattern at a time, look for matches among the loaded file paths
            for path_pattern in extraction_patterns[file_pattern_type]:
                expected_matches = extraction_patterns[file_pattern_type][path_pattern]
                path_regex = re.compile(input_dir_cont_path + "/" + path_pattern)
                # check all loaded file paths for pattern match, change the status of matchning file paths to "E" (Export)
                matching_paths = reclassify_matching_paths(path_regex, available_file_paths_dict, input_dir_cont_path)
                extraction_matches = matching_paths
                # print out a warning if too few files were found to match a given path pattern
                if (extraction_matches < expected_matches):
                    logging.warning("Too few matches found for the following path pattern: \""
                                    + input_dir_cont_path + "/" + path_pattern + "\" (" + str(expected_matches) + " matches expected, " + str(extraction_matches) + " found).")

        # go through the LocalApp path patterns for sample-wise files
        for file_pattern_type in ["sample_DNA", "sample_RNA", "sample_DNA_bcl", "sample_RNA_bcl"]:
            # if the LocalApp analysis was started from FASTQ files, skip looking for files generated from BCL input
            if ((file_pattern_type in ["sample_DNA_bcl", "sample_RNA_bcl"]) and (not from_BCL)):
                continue
            # process DNA- and RNA- specific path patterns in turn
            XNA_sample_list = DNA_sample_list
            if (file_pattern_type in ["sample_RNA", "sample_RNA_bcl"]):
                XNA_sample_list = RNA_sample_list
            for sample_id in XNA_sample_list:
                pair_id = XNA_sample_list[sample_id]["pair_id"]
                for path_pattern in extraction_patterns[file_pattern_type]:
                    expected_matches = extraction_patterns[file_pattern_type][path_pattern]
                    # fill in sample ID placeholders within the path patterns
                    sample_path_pattern = path_pattern.replace("${PAIR_ID}", pair_id).replace("${SAMPLE_ID}", sample_id)
                    path_regex = re.compile(input_dir_cont_path + "/" + sample_path_pattern)
                    # check all loaded file paths for pattern match, change the status of matchning file paths to "E" (Export)
                    matching_paths = reclassify_matching_paths(path_regex, available_file_paths_dict, input_dir_cont_path)
                    extraction_matches = matching_paths
                    # print out a warning if too few files were found to match a given path pattern
                    if (extraction_matches < expected_matches):
                        logging.warning("Too few matches found for the following path pattern for sample \"" + sample_id + "\": \""
                                        + input_dir_cont_path + "/" + sample_path_pattern + "\" (" + str(expected_matches) + " matches expected, "
                                        + str(extraction_matches) + " found).")

    # process TSOPPI data
    elif (input_type == "TSOPPI"):
        logging.info("Processing the specified TSOPPI directory data...")
        logging.info("Checking the directory content...")

        # list the paths for all files/directories within the specified TSOPPI output directory
        TSOPPI_L1_paths = glob.glob(input_dir_cont_path + "/*")

        # traverse the individual sub-paths
        for L1_path in TSOPPI_L1_paths:
            # only process further directories
            if Path(L1_path).is_dir():
                logging.info("Checking sub-directory \"" + str(Path(L1_path).name) + "\" for sample extraction eligibility...")

                # skip directories not containing file "sample_list.tsv"
                sample_list_file_path = L1_path + "/sample_list.tsv"

                if not Path(sample_list_file_path).is_file():
                    logging.warning(" - No \"sample_list.tsv\" file found. The directory will be skipped.")
                    continue
                
                logging.info(" - File \"sample_list.tsv\" found, its content will be checked for eligible samples.")

                # read in and process the sample list file
                header_read = False
                sample_list_fi = {"sample_type": -1, "sample_output_ID": -1}

                # a dictionary for keeping track of eligible samples and their types
                eligible_sample_dict = {}
                sample_count = 0    # number of samples on the sample list

                with open(sample_list_file_path, "r") as sl_infile:
                    for line in sl_infile:

                        line_s = line.strip().split("\t")

                        if (line_s[0][0] == "#"):
                            line_s = line.strip().lstrip("#").split("\t")
                            for column_id in sample_list_fi:
                                if not (column_id in line_s):
                                    logging.error("Couldn't find the required \""
                                                + column_id + "\" data field in the accessed sample list. Exiting.")
                                    exit(18)
                                sample_list_fi[column_id] = line_s.index(column_id)
                            header_read = True
                        else:
                            sample_type = line_s[sample_list_fi["sample_type"]]
                            sample_id = line_s[sample_list_fi["sample_output_ID"]]

                            sample_count += 1

                            # check whether the encountered sample ID matches any item on the input ID list
                            matching_ids = TSF.find_ID_match(sample_id, ID_prefix_list, "prefix")

                            if (len(matching_ids) == 0):
                                logging.info(" - No ID match for sample sample \"" + sample_id + "\".")
                            else:
                                # if enabled, check the InPreD ID nomenclature
                                if ((require_inpred_nomenclature) and (not TSF.is_InPreD_ID(sample_id))):
                                    logging.warning(" - The following sample ID doesn't comply with"
                                                    " the InPreD ID nomenclature: \"" + ID_string + "\"). The sample will be ignored.")
                                else:
                                    # keep track of sample IDs that pass all checks
                                    eligible_sample_dict[sample_type] = sample_id
                                    logging.info(" - ID match for sample \"" + sample_id + "\" (\"" + matching_ids[0] + "\").")
                
                # do not export files from directories that contain any samples not eligible for extraction
                if (len(eligible_sample_dict) != sample_count):
                    logging.info(" - Not all listed samples are eligible for extraction. The directory will be skipped.")
                    available_file_paths_dict = available_file_paths_dict | {L1_path: "S"}
                    continue

                logging.info(" - All listed samples are eligible for extraction. Processing the file list...")

                # load the paths of all files in given patient-wise sub-directory, set their default status to "S" (Skip)
                available_file_paths_dict_L1 = {item: "S" for item in glob.glob(L1_path + "/**", recursive = True)}
                if ((L1_path + "/") in available_file_paths_dict_L1):
                    del available_file_paths_dict_L1[L1_path + "/"]
                
                # determine valid pattern categories based on samples processed for given patient
                valid_pattern_categories = ["T_general"]
                if ("DNA_tumor" in eligible_sample_dict):
                    valid_pattern_categories.append("T_DNA_tumor")
                    if (("DNA_normal" in eligible_sample_dict) or ("RNA_tumor" in eligible_sample_dict)):
                        valid_pattern_categories.append("T_DNA_tumor_plus")
                    if ("RNA_tumor" in eligible_sample_dict):
                        valid_pattern_categories.append("T_DNA_tumor_RNA_tumor")
                if (("DNA_normal" in eligible_sample_dict) or ("DNA_tumor" in eligible_sample_dict)):
                    valid_pattern_categories.append("T_any_DNA")
                if ("DNA_normal" in eligible_sample_dict):
                    valid_pattern_categories.append("T_DNA_normal")
                if ("RNA_tumor" in eligible_sample_dict):
                    valid_pattern_categories.append("T_RNA_tumor")

                # process the patterns within individual pattern categories
                for file_pattern_type in valid_pattern_categories:
                    for path_pattern in extraction_patterns[file_pattern_type]:
                        expected_matches = extraction_patterns[file_pattern_type][path_pattern]
                        # fill in sample ID placeholders within the path patterns
                        if ("DNA_tumor" in eligible_sample_dict):
                            path_pattern = path_pattern.replace("${DT_SAMPLE_ID}", eligible_sample_dict["DNA_tumor"])
                        if ("DNA_normal" in eligible_sample_dict):
                            path_pattern = path_pattern.replace("${DN_SAMPLE_ID}", eligible_sample_dict["DNA_normal"])
                        if ("RNA_tumor" in eligible_sample_dict):
                            path_pattern = path_pattern.replace("${RT_SAMPLE_ID}", eligible_sample_dict["RNA_tumor"])
                        path_regex = re.compile(L1_path + "/" + path_pattern)
                        # check all loaded file paths for pattern match, change the status of matchning file paths to "E" (Export)
                        matching_paths = reclassify_matching_paths(path_regex, available_file_paths_dict_L1, input_dir_cont_path)
                        extraction_matches = matching_paths
                        # print out a warning if too few files were found to match a given path pattern
                        if (extraction_matches < expected_matches):
                            logging.warning(" - Too few matches found for the following path pattern: \""
                                            + input_dir_cont_path + "/" + path_pattern + "\" (" + str(expected_matches) + " matches expected, " + str(extraction_matches) + " found).")

                # extend the overal TSOPPI path dictionary with file path information for given patient
                available_file_paths_dict = available_file_paths_dict | available_file_paths_dict_L1
            else:
                available_file_paths_dict = available_file_paths_dict | {L1_path: "S"}

    # create the output files
    # - a list of files/paths eligible for export
    # - a list of files/paths that should be skipped during the extraction
    # the reported paths are relative (starting with the LocalApp/TSOPPI directory)
    skipped_file_count = 0
    selected_file_count = 0
    ignored_directory_count = 0

    logging.info("Creating output files...")
    with open(skipped_file_path_list_cont, "w") as sfp_outfile, \
            open(outfile_file_path_list_cont, "w") as efp_outfile:
        for fp_record in available_file_paths_dict:
            (prefix_present, fp_record_ps) = TSF.strip_path_prefix(fp_record, input_dir_cont_path + "/")
            if not prefix_present:
                logging.error(TSF.get_path_prefix_error_message("LocalApp file",
                                                            fp_record,
                                                            base_dir_path))
                exit(19)
            
            status_code = available_file_paths_dict[fp_record]
            if (status_code == "S"):
                sfp_outfile.write(outfile_dir_name + "/" + fp_record_ps + "\n")
                skipped_file_count += 1
            elif(status_code == "E"):
                efp_outfile.write(outfile_dir_name + "/" + fp_record_ps + "\n")
                selected_file_count += 1 
            elif (status_code == "I"):
                ignored_directory_count += 1
            else:
                logging.error("Unexpected skip/export status for file path \"" + fp_record + "\" (status code: \"" + status_code + "\"). Exiting.")
                exit(20)

    # create a bash script that runs tar, gpg and md5sum on files eligible for export
    # - md5sum is run on regular files only (not directories)
    if (selected_file_count > 0):
        with open(outfile_script_path_cont, "w") as esp_outfile:
            optional_ampersand = ""
            if parallel_export_and_md5sum:
                optional_ampersand = " &"

            esp_outfile.write("#!/bin/bash\n")
            esp_outfile.write("date\n")
            esp_outfile.write("echo \"setting up dedicated stdout and stderr log files..\"\n")
            esp_outfile.write("exec >  >(tee -i {})\n".format(outfile_script_stdout_log_path))
            esp_outfile.write("exec 2> >(tee -i {} >&2)\n".format(outfile_script_stderr_log_path))
            esp_outfile.write("sleep 2\n")
            esp_outfile.write("echo \"packaging and encrypting selected files..\"\n")
            esp_outfile.write("if [ -f {0} ]; then rm {0} ; fi\n".format(outfile_archive_path))
            esp_outfile.write("tar -C {} -T {} -c | gpg -c --passphrase-file {} --batch --cipher-algo aes256 -o {}{}\n".format(
                              outfile_dir_parent_path, outfile_file_path_list, outfile_password_path, outfile_archive_path, optional_ampersand))
            if archive_level_md5sum:
                esp_outfile.write("echo \"creating archive-level md5 checksums..\"\n")
                esp_outfile.write("md5sum {} > {}{}\n".format(outfile_archive_path, outfile_archive_level_md5_path, optional_ampersand))
            else:
                esp_outfile.write("echo \"creating file-level md5 checksums..\"\n")
                esp_outfile.write("cd {}\n".format(outfile_dir_parent_path))
                esp_outfile.write("cat {} | while read path_line; do if [ -f ${{path_line}} ]; then md5sum ${{path_line}}; fi; done > {}{}\n".format(
                                  outfile_file_path_list, outfile_file_level_md5_path, optional_ampersand))
                esp_outfile.write("cd - > /dev/null\n")
            if parallel_export_and_md5sum:
                esp_outfile.write("wait\n")
            esp_outfile.write("date\n")

        # if enabled, run the tar/gpg/md5sum bash script
        if not generate_export_script_only:
            logging.info("Running the data extraction, packaging and ecryption...")
            subprocess.run(["bash", outfile_script_path_cont])
    else:
        logging.info("No files qualified for extraction. Exiting.")
        exit(0)

if __name__ == '__main__':
    main()
