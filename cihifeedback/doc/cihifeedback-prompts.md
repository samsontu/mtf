# Populate the WHO Mapping Feedback template with feedback based on CIHI mappings, 

```markdown
Develop a plan to generate entries of a target spreadsheet based on data from a source spreadsheet. The columns of the target spreadsheet are based on a template spreadsheet.
1. Read source spreadsheet = 'AllBatches_ForSamson_V1clean.xlsx'
2. Read template spreadsheet = '/Users/tu/Documents/Dropbox/WHO (1)/Mapping Task Force/WHO-ICD-10-11-Mapping Local Workspace/CIHIMapBasedValidation/WHO_Mapping Feedback Template_V2.0.xlsx' 
3. Use the columns in the 'Feedback Template' sheet of the template for the target spreadsheet
4. In the source spreadsheet, use the values of row 1 as the column name references. 
5. We will map two rows of the source spreadsheet to one row of the target spreadsheet, starting with rows 2 and 3 of source mapping to first entry of the target spreadsheet.
6. For each pair of source rows, verify that columns A - G have the same values. If so, map them as follows:
| Target column | Source | Notes |
|---|---|---|
| A Organization/Affiliation | static "CIHI" | |
| B Date | static 2025-07-04 | |
| C Name | static "Sharon Baker" | |
| D Contact Details | static "whofic.mtf@gmail.com" | |
| E Version of WHO Mapping Table | static "2022 10To11MapToOneCategory" | |
| F Map direction | static "Forward (ICD-10 to ICD-11)" | |
| G WHO ICD-10/11 Code | A WHO_icd10Code | source side of the map |
| H WHO ICD-10/11 Code Title | B WHO_icd10Title | |
| I WHO Mapped ICD-10/11 Code | D Updated WHO_icd11Code | what WHO currently maps to |
| J WHO Mapped ICD-10/11 Title | E Updated WHO_icd11Title | |
If they are not the same, generate an error message showing the discrepancies
7. For other target columns, we have the following cases:
a. both rows of source column H (Reviewer Choice) or both values of column M (Conflict Resolution team decision) or at least one value of column Q (Comments from Eva) are  "WHO 2024 map correct" or the value includes "WHO map correct" or column M is "D37-D48 Exclusion" or column B (WHO_icd10Title) contains "Neoplasm of uncertain or unknown behaviour"
b. both values of column H (Reviewer choice) or both values of column M (Conflict Resolution team decision)  have the value "CIHI map correct" or  one of the values of column Q contains both "CIHI" and "correct"
c. both values of column H (Reviewer choice) are "Neither correct" and the value of column I (Agree) is "Agree"
d. both values of column M (Conflict Resolution team decision) are "Neither correct"
e. both values of column M (Conflict Resolution team decision) are "Review" or "Review with Eva" and cases b and c do not hold
Verify that cases a - e cover all rows of the source spreadsheet. If that's not the case, output the rows not covered by the cases in an Excel file named rowsNeedReview.xlsx. Also output to rowsNeedReview.xlsx (instead of the target spreadsheet) any row whose Suggested/Corrected Mapped ICD-10 /ICD-11 Code is not a valid ICD-11 code or code cluster (e.g., stray text string), or that contains a code not found in the most recent ICD-11 MMS release (look it up with the WHO ICD API and ask the user to confirm the release first). For those rows covered by the cases, do the following:
8.a In case a (WHO map correct), add nothing to the target spreadsheet
8.b In case b (CIHI map correct), map the rest of the columns as follows:
| K Suggested/Corrected Mapped Code | R CIHI ICD-11 code | CIHI's preferred code |
| L Suggested/Corrected Mapped Code Title |blank | |
| M Corrected Code Mapping Relation | W Equivalence | E→Equivalent / B→Broader / N→Narrower |
| N Comment | concatenate O Comments (only one of two rows if values are the same)+ L Comment and Explanation  (both rows)| + Q (comments from Eva) if values of the two rows are different) |
| O WHO Mapped Foundation Entity | blank | not in source |
| P Suggested/Corrected Foundation Entity | blank | not in source |
| Q Additional Comments | T Reason for No Match to WHO map | or blank |
| R Action for WHO | P Actions for WHO if column P has a value that is not "Review with Eva", otherwise add "update WHO map"| |
| S Details | blank | |
| T Status | blank | leave for WHO to fill |
8.c In case c "Neither correct" and reviewers agree, map the rest of the columns as follows:
| K Suggested/Corrected Mapped Code | K Reviewer ICD-11 coding if neither correct | reviewers' code |
| L Suggested/Corrected Mapped Code Title | blank | |
| M Corrected Code Mapping Relation | blank |
| N Comment | concatenate both rows of L Comment and Explanation  | |
| O WHO Mapped Foundation Entity | blank | not in source |
| P Suggested/Corrected Foundation Entity | blank | not in source |
| Q Additional Comments | blank |
| R Action for WHO | "Update map" | |
| S Details | blank | |
| T Status | blank | leave for WHO to fill |
8.d In case d (conflict resolution's proposed coding), map the rest of the columns as follows:
| K Suggested/Corrected Mapped Code | N Review team ICD-11 coding if neither correct | reviewers' code |
| L Suggested/Corrected Mapped Code Title | blank| |
| M Corrected Code Mapping Relation | blank |
| N Comment | Column O Comments  | |
| O WHO Mapped Foundation Entity | blank | not in source |
| P Suggested/Corrected Foundation Entity | blank | not in source |
| Q Additional Comments | blank |
| R Action for WHO | Column P Actions for WHO | |
| S Details | blank | |
| T Status | blank | leave for WHO to fill |
8.e In case e "Review" or "Review with Eva" , map the rest of the columns as follows:
| K Suggested/Corrected Mapped Code | blank |  |
| L Suggested/Corrected Mapped Code Title | blank| |
| M Corrected Code Mapping Relation | blank |
| N Comment | Concatenae Column O Comments and Column Q |  |
| O WHO Mapped Foundation Entity | blank | not in source |
| P Suggested/Corrected Foundation Entity | blank | not in source |
| Q Additional Comments | blank |
| R Action for WHO | Column P Actions for WHO | |
| S Details | blank | |
| T Status | blank | leave for WHO to fill |

# Check CIHI-based validation corrections against  2026 mapping table 

1. Extract from WHO_Mapping_Feedback_CIHI_AllBatches.xlsx those rows that have values for column K and write them to rowsWithSuggestedCode.xlsx

2. Read 2026_10To11MapToOneCategory.xlsx . For entries in rowsWithSuggestedcode.xlsx (1), find the corresponding entry in 2026_10To11MapToOneCategory.xlsx (2) by matching column H in (1) with column C in (2).  Check to see if the suggested code (column K of 1) is the same as the icd11code (column J of 2). If they are the same, write the entry to a file CIHISuggestedCodesFixedIn2026Release.xlsx

3. Generate a new file WHO_Mapping_Feedback_CIHI_Unfixed2026_AllBatches.xlsx from WHO_Mapping_Feedback_CIHI_AllBatches.xlsx by removing the entries in CIHISuggestedCodesFixedIn2026Release.xlsx

4. Regenerate the rowsWithSuggestedcode from WHO_Mapping_Feedback_CIHI_Unfixed2026_AllBatches.xlsx 

