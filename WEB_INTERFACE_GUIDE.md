# Espresso Web Interface - Deployment & Usage Guide

## ✨ What's New (Phase 6)

The Espresso platform now features a modern, chat-style web interface with advanced styling:

### Key Features
- **Interactive Chat Interface**: Select a dataset and ask statistical questions in natural language
- **Real-time Analysis**: Diagnostics, model execution, and AI interpretation happen live
- **Bullet-Point Results**: Simplified, client-facing interpretation format with quantitative details
- **Advanced Styling**: White and latte brown color scheme with sophisticated animations
- **History Tracking**: Recent analyses stored and accessible for quick reference
- **Responsive Design**: Works on desktop, tablet, and mobile devices

---

## 🚀 Quick Start

### Prerequisites
```bash
# Ensure Python 3.10+ is installed
python --version

# Required packages (install if not already present)
pip install flask pandas numpy scipy google-genai
```

### Starting the Application

1. **Navigate to the project directory**:
   ```bash
   cd c:\Users\vibho\Documents\espresso-prototype
   ```

2. **Start the Flask server**:
   ```bash
   python app.py
   ```
   
   You should see:
   ```
   ============================================================
   ESPRESSO - Advanced Statistical Analysis Platform
   ============================================================
   Starting web interface on http://localhost:5000
   ============================================================
   ```

3. **Open your browser**:
   - Navigate to: `http://localhost:5000`
   - Or open: [http://localhost:5000](http://localhost:5000)

---

## 📊 Using the Interface

### 1. **Select a Dataset**
   - Use the dropdown in the left sidebar
   - Choose from available CSV files in the `data/` folder
   - Current datasets supported:
     - `test_causal.csv` - Panel data for causal analysis (DiD)
     - `test_panel.csv` - Panel structure data
     - `dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF.RES_WEO_9.0.0.csv` - IMF economic data

### 2. **Ask a Question**
   Type your statistical question in the input field. Examples:
   
   **For Causal Analysis (DiD)**:
   - "Does higher fiscal deficit slow down GDP growth?"
   - "Does treatment cause outcome increase?"
   - "What is the effect of policy on employment?"
   
   **For Forecasting (ARIMA)**:
   - "What will be the forecast for GDP growth next period?"
   - "Predict next year's inflation rate"
   - "What's the forecast for the next time period?"

### 3. **View Results**
   Results display in a modal with four sections:
   
   #### Pre-Analysis Diagnostics
   - Shows statistical violations detected
   - Lists corrections automatically applied
   - Explains diagnostic issues and recommendations
   
   #### Key Statistics
   - **For DiD**: Treatment effect, standard error, p-value, R-squared
   - **For ARIMA**: Forecast, AR coefficient, RMSE
   
   #### AI-Powered Interpretation
   - **Direct Answer**: YES/NO/UNCLEAR to your question
   - **Statistical Significance**: P-value and threshold comparison
   - **Effect Magnitude**: Size and interpretation
   - **Confidence Level**: 95% CI and zero inclusion check
   - **Model Fit**: R-squared and quality assessment
   - **Practical Meaning**: Plain language explanation
   - **Key Limitations**: Caveats and uncertainties
   - **Diagnostic Issues**: Violations and corrections applied

### 4. **Review History**
   - Recent analyses appear in the sidebar
   - Click any history item to reload that analysis
   - History automatically updates with each new analysis

---

## 🎨 Interface Design

### Color Scheme
The platform uses an advanced white and latte brown aesthetic:
- **Base**: Pure white (#FFFFFF)
- **Primary**: Latte brown (#C4A57B)
- **Secondary**: Warm brown (#E8DCC8)
- **Accents**: Deep brown (#8B6F47), Warm accents (#D4A574)

### Layout Components
- **Sidebar** (Left): Dataset selection, recent history, branding
- **Chat Area** (Main): Messages, welcome screen, input field
- **Modal** (Overlay): Detailed results with statistics and interpretation
- **Loading Spinner**: Indicates analysis in progress

---

## 🔧 Architecture

### Backend (Python/Flask)
- **app.py**: Main Flask application (170 lines)
  - Routes: `GET /`, `POST /api/analyze`, `GET /api/history`, `GET /api/datasets`
  - Full pipeline integration (load → parse → map → diagnose → model → interpret)
  - JSON API responses for seamless frontend integration

- **Core Modules** (unchanged from Phase 5):
  - `llm.py`: LLM question parsing and column mapping
  - `models.py`: DiD and ARIMA implementations
  - `diagnostics.py`: 5 pre-analysis statistical tests
  - `interpretation.py`: **NEW bullet-point format** for client-facing results
  - `selector.py`: Automatic model selection logic

### Frontend (HTML/CSS/JavaScript)
- **templates/index.html**: Chat-style interface (105 lines)
- **static/style.css**: Advanced styling with animations (550+ lines)
- **static/script.js**: **NEW** Interactive JavaScript logic (430 lines)
  - Dataset and question handling
  - API communication
  - Results display and formatting
  - History management
  - Loading states and animations

---

## 📝 Interpretation Format (Phase 6 Change)

The LLM interpretation has been completely redesigned for clarity:

### OLD Format (Phase 5)
```
Based on a Difference-in-Differences statistical analysis, 
here's an interpretation of the results...
[5-point prose explanation]
```

### NEW Format (Phase 6) ✨
```
• **Direct Answer**: The treatment has a statistically significant negative effect on GDP growth.

• **Statistical Significance**: Yes, p-value = 0.0241 (below 0.05 threshold)

• **Effect Magnitude**: -0.0047 percentage points (approximately 0.47% decrease)

• **Confidence Level**: 95% CI: [-0.0087, -0.0008] (excludes zero)

• **Model Fit**: R² = 0.847 (85% of variation explained - very strong fit)

• **Practical Meaning**: Every unit increase in fiscal deficit is associated with a 0.47% 
decrease in GDP growth, holding other factors constant.

• **Key Limitations**: 4.1% chance of random variation; strong model fit suggests reliable 
relationships; heteroscedasticity and autocorrelation detected.

• **Diagnostic Issues Detected**: Heteroscedasticity and autocorrelation violations corrected 
using robust standard errors; residuals show slight non-normality.
```

---

## 🧪 Testing the System

### Test Case 1: Causal Analysis (DiD)
```
Dataset: test_causal.csv
Question: "Does higher fiscal deficit slow down GDP growth?"

Expected Results:
- Model: DiD (Difference-in-Differences)
- Effect: ~0.47pp (numeric value varies with data)
- P-value: ~0.27 (not significant)
- Status: Analysis completes successfully
```

### Test Case 2: IMF Data - Causal
```
Dataset: dataset_2026-01-29T20_09_46.399406532Z_DEFAULT_INTEGRATION_IMF...csv
Question: "Does higher fiscal deficit slow down GDP growth?"

Expected Results:
- Model: DiD
- Data points: 8,208 rows × 116 columns
- Status: Completes with diagnostics
```

### Test Case 3: IMF Data - Forecast
```
Dataset: [Same IMF dataset]
Question: "What will be the forecast for GDP growth in next period?"

Expected Results:
- Model: ARIMA (if ARIMA format recognized)
- Status: Tests data structure suitability for time-series models
```

---

## 🐛 Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'google.genai'"
**Solution**: Install required packages
```bash
python -m pip install google-genai
```

### Issue: Port 5000 already in use
**Solution**: Change port in app.py (line 201)
```python
app.run(debug=True, port=5001)  # Use different port
```
Then access: http://localhost:5001

### Issue: "Dataset not found"
**Solution**: Ensure CSV files are in the `data/` folder
```bash
ls data/  # List files
```

### Issue: Slow analysis
**Reason**: Initial run involves LLM API calls (Gemini) which take 2-5 seconds
**Solution**: This is normal; subsequent runs may be faster with caching

### Issue: Results don't show in modal
**Solution**: 
1. Check browser console (F12 → Console tab)
2. Ensure JavaScript is enabled
3. Clear browser cache and refresh

---

## 📈 Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Load page | <1s | Instant HTML/CSS |
| Load datasets | <1s | Directory scan |
| DiD Analysis | 3-5s | LLM interpretation adds delay |
| ARIMA Forecast | 2-3s | Faster, no LLM needed (can add) |
| Load history | <1s | In-memory retrieval |

---

## 🔐 Privacy & Safety

- **Local Processing**: All analysis runs on your machine
- **API Key**: Google Gemini API key needed (in `llm.py`)
- **No Data Upload**: Files processed locally, not sent to cloud (except LLM queries)
- **History**: Stored in memory, cleared on server restart

---

## 📚 File Structure

```
espresso-prototype/
├── app.py                           # Flask web server (NEW)
├── templates/
│   └── index.html                  # Chat interface (NEW)
├── static/
│   ├── style.css                   # Advanced styling (NEW)
│   └── script.js                   # Frontend logic (NEW)
├── interpretation.py                # Updated for bullet-points (MODIFIED)
├── llm.py                          # LLM integration
├── models.py                        # DiD & ARIMA
├── diagnostics.py                   # Pre-analysis tests
├── selector.py                      # Model selection
├── data_utils.py                    # Data loading
├── data/
│   ├── test_causal.csv
│   ├── test_panel.csv
│   └── [IMF datasets...]
└── outputs/                         # (Legacy, not used in web interface)
```

---

## 🎯 Next Steps

Future enhancements:
1. **Visualizations**: Chart.js integration for effect plots and confidence intervals
2. **Data Upload**: File upload UI instead of fixed datasets
3. **Batch Analysis**: Run multiple questions sequentially
4. **Report Export**: Download results as PDF or DOCX
5. **Advanced Options**: Adjust model parameters and diagnostic settings
6. **API Documentation**: OpenAPI/Swagger documentation for programmatic access

---

## 📞 Support

For issues or questions:
1. Check the browser console for JavaScript errors (F12)
2. Check terminal output for Python errors
3. Verify all dependencies are installed
4. Ensure Flask server is running (check terminal)
5. Try refreshing the page (Ctrl+F5)

---

**Espresso v1.0 - Statistical Analysis Made Accessible**
*Powered by Python, Flask, and AI Understanding*

Last Updated: January 31, 2025
