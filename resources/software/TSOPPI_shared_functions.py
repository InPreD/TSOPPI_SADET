"""Functions used by TSOPPI python scripts."""
import re
from typing import List, Tuple


def get_SADET_version():
    return("0.1.0:2024-12-08")


def get_path_prefix_error_message(file_description: str,
                                  file_path: str,
                                  path_prefix: str) -> str:
    """Print an error message about missing HS prefix in the file path."""
    error_message = "Provided " + file_description + " path (\"" + file_path + "\") does not include the specified directory prefix (\"" + path_prefix + "\"). Exiting.\n"
    return(error_message)


def get_file_not_found_error_message(file_description: str,
                                     file_path: str) -> str:
    """Print an error message about given file/directory not existing."""
    error_message = "Specified " + file_description + "(\"" + file_path + "\") couldn't be located within the container. Exiting.\n"
    return(error_message)


def convert_path(current_file_path: str,
                 current_prefix: str,
                 target_prefix: str) -> Tuple[bool, str]:
    """Convert a host-system file path to a container file path, or vice versa."""
    # - check whether the current file path contains the current prefix
    # - if so, replace the current prefix with the target one
    current_prefix_present = False
    container_file_path = "NA"
    if (current_file_path.startswith(current_prefix)):
        current_prefix_present = True
        container_file_path = target_prefix + current_file_path[
                                                len(current_prefix):]
    return(current_prefix_present, container_file_path)


def strip_path_prefix(file_path: str,
                      path_prefix: str) -> Tuple[bool, str]:
    """Remove specified prefix from the given file path."""
    # - check whether the given file path contains the supplied prefix
    # - return the given file path with the prefix removed
    prefix_present = False
    stripped_path = "NA"
    if (file_path.startswith(path_prefix)):
        prefix_present = True
        stripped_path = file_path[len(path_prefix):]
    return(prefix_present, stripped_path)


def check_file_list_size(file_list: List[str], file_type: str, file_path_pattern: str,
                         error_code: int) -> Tuple[int, str]:
    """Check whether a single file was found for given path pattern. Return an error value and message depending on the status."""

    return_value = 0
    return_message = 0

    if (len(file_list) == 0):
        return_message = " - No " + file_type + " found at the expected location (\"" + file_path_pattern + "\"). Single file. Exiting."
        return_value = error_code
    elif (len(file_list) > 1):
        return_message = " - Multiple " + file_type + "s found at the expected location (\"" + file_path_pattern + "\"). Single file. Exiting."
        return_value = error_code
    else:
        return_message = " - The following " + file_type + " will be utilized: \"" + file_list[0] + "\"."
        return_value = 0

    return(return_value, return_message)


def find_ID_match(sample_id: str, approved_ids: List[str], method: str) -> List[str]:
    """Find and report an approved ID that matches given sample_id."""
    matching_id_list = []

    # find an approved ID that is a prefix of given sample ID
    if (method == "prefix"):
        matching_id_list = [id_candidate for id_candidate in approved_ids if sample_id.startswith(id_candidate)]
   
    return(matching_id_list)


def is_InPreD_ID(input_ID: str) -> bool:
    """Check whether the supplied string value is a valid InPreD ID."""

    # InPreD nomenclature version 3
    id_regex = re.compile("^IP[ADHO][0-9]{4}-[CDR](0[1-7]|50|51)-[ACDdEeLMNPpRrTX][0-9]{2}-[ABCEFMS]([0-2][0-9]|30|XX)$")

    return(re.match(id_regex, input_ID) is not None)