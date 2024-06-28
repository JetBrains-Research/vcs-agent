# Version Control System (VCS) Agent
## Data scraping
In `src` you can find the code for the `RepositoryDataScraper`. In `main.py` you can see how to use the class.

The repositories that we consider are sourced from [SEART](https://seart-ghs.si.usi.ch/) with the following filters:
- Last commit between: 01/01/2020 - 31/05/2024
- Branches ≥ 5
- Contributors ≥ 2
- Stars ≥ 50
- Exclude forks TRUE
- Has License TRUE

We manually download the metadata from [SEART](https://seart-ghs.si.usi.ch/) and then programmatically clone 
the repositories, before using `RepositoryDataScraper` to scrape them.

In doing so, we mine samples for the following agent scenarios:
- Subsequent commits modifying the same file (file-commit grams)
- Merging
- Cherry-picking