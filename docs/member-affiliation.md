# Member chapter, country and region

Members can edit Chapter, Country and Region in **Edit my information**. Chapter is free text; Country retains the existing country entry and alias handling. Region is selected from the seven organizational regions. These fields appear separately on member cards and detail pages.

The directory supports combined chapter, country and region filters. Filters run before pagination. Map counts respect search, chapter and region; selecting a country narrows the member list as before.

Personal edits are stored in `SelfEdits` and survive source synchronization. Optional `Chapter` and `Region` spreadsheet/import columns are supported. Existing records require no database migration and display unassigned fields until supplied. Regions are manually assigned, not inferred from geography. India can remain unassigned because the supplied definitions exclude it from Asia without specifying another region.

Region choices: North America, South America, Europe, Africa, Asia, Middle East and Oceania. The editor explains the geographic definitions. The API validates the choice, rejects India and the twelve Middle East countries under Asia, and restricts Middle East to Iraq, Iran, Saudi Arabia, Kuwait, Oman, Bahrain, Lebanon, Yemen, Syria, Jordan, Qatar and United Arab Emirates. Other continental assignments are selected by the member.

`GET /members` accepts `chapter`, `country` and `region`, and returns `chapters`, `countries` and `regions` for filter options.
