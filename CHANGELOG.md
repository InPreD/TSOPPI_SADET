# Change Log
All notable changes to this project should be documented in this file.
 
The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).
 
## [Unreleased]

Changes made during the development since the last release. (last update: 2025-03-11)

### Added

### Changed

### Fixed

## Initial production version ["release 1.0.0"] - 2025-03-20

### Added
- Devcontainer setup added. [#9](https://github.com/InPreD/TSOPPI_SADET/issues/9)
- Added DockerHub build and push action. [#5](https://github.com/InPreD/TSOPPI_SADET/issues/5)
- SADET.py's directory added to the PATH variable. [#7](https://github.com/InPreD/TSOPPI_SADET/issues/7)
- Shebang added to the SADET.py script. [#7](https://github.com/InPreD/TSOPPI_SADET/issues/7)
- Shebang added to the output bash export script. [#15](https://github.com/InPreD/TSOPPI_SADET/issues/15)
- Added an option `--parallel_export_and_md5sum` for parallelizing the gpg/tar and md5sum steps within the bash export script. [20](https://github.com/InPreD/TSOPPI_SADET/issues/20)
- Added creation of log files to the bash export script.
 
### Changed
- Changed to a smaller Docker image (`python:3.14.0a2` -> `python:3.14.0a2-slim`). [#10](https://github.com/InPreD/TSOPPI_SADET/issues/10)
- Various adjustments to the log output formatting.
- Adjusted SADET's definition of the InPreD sample nomenclature in order to reflect the latest change introduced to the TSOPPI [nomenclature page](https://tsoppi.readthedocs.io/en/latest/inpred_nomenclature.html): Allowing unknown sample material type (code "X").
- Adjusted the logging levels of selected log messages (`INFO` to `WARNING` and vice-versa).
   
### Fixed
- Fixed `TypeError` caused by missing integer-to-string conversion. [#19](https://github.com/InPreD/TSOPPI_SADET/issues/19)
- Prevented SADET from exiting when encountering irrelevant subdirectories in TSOPPI result directory (such directories are now skipped). [#21](https://github.com/InPreD/TSOPPI_SADET/issues/21)
- Prevented export of incorrect LocalApp output *csv files. [#29](https://github.com/InPreD/TSOPPI_SADET/issues/29)
- Enabled export of correct LocalApp output files regardless of Pair_ID sample sheet formatting. [#30](https://github.com/InPreD/TSOPPI_SADET/issues/30)
- Enabled export of mutational signature PCGR results.
- Added missing timestamps and logging level information to the log files created by SADET. (#32)[https://github.com/InPreD/TSOPPI_SADET/issues/32]
- Allowed certain log files to be missing from the LocalApp output (setting the minimum expected file-counts for these to 0).
- Accounted for the possibility of the LocalApp creating seperate Log and Report files for DNA and RNA samples during BCL input demultiplexing.
- Accounted for LocalApp runs that analyze only DNA samples or only RNA samples (potentially an incomplete fix by now).
 
## Initial test version [commit [`8507a30`](https://github.com/InPreD/TSOPPI_SADET/commit/8507a303ef5789f5ac6a656992c09547071da39e)] - 2024-12-08
 
### Added
- Initial functionality.
