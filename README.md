# Version Control System (VCS) Agent
## Data scraping
In `src` you can find the code for the `RepositoryDataScraper`. In `main.py` you can see how to use the class.

The repositories that we consider are sourced from [SEART](https://seart-ghs.si.usi.ch/) with the following filters:
- Last commit between: 01/01/2020 - 31/05/2024
- Branches ≥ 5
- Contributors ≥ 10
- Stars ≥ 100
- Exclude forks TRUE
- Has License TRUE
    - Specifically one of: MIT License, Apache License 2.0, BSD 3-Clause "New" or "Revised" License, BSD 2-Clause "Simplified" License

We manually download the metadata from [SEART](https://seart-ghs.si.usi.ch/) and then programmatically clone 
the repositories, before using `RepositoryDataScraper` to scrape them.

In doing so, we mine samples for the following agent scenarios:
- Subsequent commits modifying the same file (file-commit grams)
- Merging
- Cherry-picking

## Setup
You can use the `RepositoryDataScraper` to scrape your own repository or you perhaps would like to extend it
to mine additional scenarios for AI Agents. In either case, follow the setup instructions in this section to
setup and run the system locally.

## File Structure
Some files are just included for documentation purposes, such as `src/notebooks/analyze_dataset.ipynb` for which
the raw dataset .csv is not included. We will probably release the dataset on HuggingFace at a later point.



## Known issues
### unable to create file: Filename too long error
This issue can occur on Windows, since the new maximum length for file names is opt-in. Please refer to this 
[documentation on how to fix the issue](https://confluence.atlassian.com/bamkb/git-checkouts-fail-on-windows-with-filename-too-long-error-unable-to-create-file-errors-867363792.html).
We recommend setting the git workaround, as we still had issue after updating the registry key and restarting.