# Real Survey Data Files

This folder is for uploading real-life GPS survey data files for testing TinForge.

## Supported Formats

- **CSV/TXT**: Point lists with X, Y, Z coordinates (ID, X, Y, Z, Description)
- **PDF**: Survey reports with coordinate tables or listings
- **Topcon Exports**: Native Topcon survey data files
- **Licai Exports**: Licai system survey data files

## Upload Instructions

1. Push your survey data files to this folder via GitHub
2. Supported file types:
   - `*.csv` - Comma-separated values
   - `*.txt` - Tab or space-separated text
   - `*.pdf` - PDF survey reports
   - `*.tp3`, `*.tin` - Topcon format files
   - `*.dat` - Licai format files

## Files Structure

```
real_survey_data/
├── topcon_surveys/      # Topcon system exports
├── licai_surveys/       # Licai system exports
├── csv_data/            # CSV/TXT point files
└── pdf_reports/         # PDF coordinate reports
```

## Testing Workflow

Once files are uploaded:
1. Navigate to the file in GitHub
2. Notify me of the file path
3. I'll run TinForge tests using your real data
4. Export results to both Topcon and Licai formats
5. Show you the validated output

---

**Ready to upload your survey files!** 📁
