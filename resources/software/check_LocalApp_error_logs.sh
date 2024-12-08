# version 0.1 [2024-12-04]
# print non-INFO lines containing the "error" (case non-sensitive) string from LocalApp's output directory (the directory needs to be specified by its full path)
# recommended use: 'bash check_LocalApp_error_logs.sh <LocalApp_dir_path>'

if [ $# -ne 1 ]
then
  echo "[LocalApp error checking script - ERROR] Exactly one parameter is expected (the path to the LocalApp output directory), but $# were supplied. Exiting."
  exit 1
fi

LOCALAPP_DIR_PATH=$1

if [ ! -d ${LOCALAPP_DIR_PATH} ]
then
  echo "[LocalApp error checking script - ERROR] The spcified LocalApp output directory (\"${LOCALAPP_DIR_PATH}\") wasn't found. Exiting."
  exit 2
fi

# check for errors, filter out log INFO lines
cd ${LOCALAPP_DIR_PATH} > /dev/null
grep -i "error" Logs_Intermediates/*/* | grep -v "INFO"
cd - > /dev/null
