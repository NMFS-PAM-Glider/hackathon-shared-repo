# ![](glider-reporter-logo.png)

## A Flexible Template for Building Markdown Reports for Underwater Oceanographic Gliders

## Collaborators

**Shannon Rankin:** Southwest Fisheries Science Center [Project & Process Ideation]

**AI Agents:** Gemini [create prompts for copilot]; Github CoPilot [prompts–\> process]

Hackweek Participants: [cite those added a function or we used their function during rodeo]

**Crowdsourced:**TBD-- This will be created at a later date

## Dashboard & Repository

![](glider-reporter_screenshot.png)

[glider-reporter site & dashboards](https://shannonrankin.github.io/glider-reporter/); [Github Repo](https://github.com/shannonrankin/glider-reporter/tree/main)

## Background

## Goals

Develop a shared repository and interactive site for crowdsource functions useful to underwater oceanographic glider operations, including: - Custom Issue template for crowdsourced contribution to ideation and development of functions (for data analysis, visualizations, tables, etc) - Allow user to search and find preliminary functions coded in R and/or Python - Allow user to apply their data to align fields and preview output - Allow user to download markdown file with function(s) and identified dependencies - ??

## Methods

1.  Process/System Ideation (Shannon, wee early hours of September 16!)
2.  Create blank [glider-reporter repository](https://github.com/shannonrankin/glider-reporter) with starter .github/copilot-instructions.rmd
3.  Create Prompts (Shannon's works with Gemini to turn her mad braindump into a series of Prompts to turn into issues to work with Github CoPilot:
4.  Github Copilot via Issues (run in browser):
    1.  [Issue#1 Setup Base Repo Structure & Standards](https://github.com/shannonrankin/glider-reporter/issues/1) (CoPilot ChatGPT Luna 5.6, 4 credits)
    2.  [Issue#3 Function Issue Form Template, Registry Generator & Sample Reporting Function](https://github.com/shannonrankin/glider-reporter/issues/3) (Chat GPT Sol 5.6, 49 credits w/ additional issues to address errors)
    3.  [Issue#7 Data Intake & Interactive Field Matching Engine (Quarto + ObservableJS)](https://github.com/shannonrankin/glider-reporter/issues/7) (Chat GPT Sol 5.6, 159 credits)
    4.  [Issue#9 Interactive Function Explorer Dashboard (Quarto + ObservableJS)](https://github.com/shannonrankin/glider-reporter/issues/9) (Chat GPT Sol 5.6, 83 credits)
    5.  [Issue#11 Interactive Report Builder Dashboard & Client-Side Bundle Exporter (Quarto + ObservableJS)](https://github.com/shannonrankin/glider-reporter/issues/11https://github.com/shannonrankin/glider-reporter/issues/11) (Chat GPT Sol 5.6, 111 credits)
    6.  [Issue#13 Website Navigation, Documentation Interface & Citation/AI Reference Page](https://github.com/shannonrankin/glider-reporter/issues/13) (Chat GPT Sol 5.6, 61 credits)
5.  Review site, update \_quarto.yml, build github pages, etc.

### Datasets

Options:

- Sample Test Dataset (OG1.0)
- If user dataset, they will match fields to standardized datasets (as needed)
- Option to also include GliderDAC/ERDDAP

### Workflow

**Github Repository:** glider-reporter (<https://github.com/shannonrankin/glider-reporter>)

![](glider-reporter.drawio.png)

## Next Steps

The initial sketch and infrastructure of this plan were developed during the Hackathon but without a team. Next steps include (1) improving infrastructure and documentation (solo), (2) creating a x-reporter template for use for other communities, and (3) working with the UG2 community to develop the glider-reporter for this community.

## References

## Acknowledgements

This project was part of a [Glider Rodeo Hackathon](https://nmfs-pam-glider.github.io/GliderRodeo/hackathon/) which worked with (or was inspired by) PAM-Glider data collected by the NOAA Fisheries Glider Rodeo (2026). This weeklong event was hosted by NOAA Fisheries with support by Openscapes (JupyterHub, Support), Oregon State University (Zoom, Box data storage), Aquaview (technical support).
