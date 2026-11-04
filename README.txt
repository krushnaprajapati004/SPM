FarmPro — Python + SQLite + AI Farm Management System
=====================================================

FEATURES
- Python Flask backend
- SQLite database (farmpro.db is created automatically on first run)
- User sign-up, login and logout with password hashing and server sessions
- Persistent crop, labor, inventory, expense and sales records
- Settings stored in the database (profile and light/dark theme)
- Database-backed notifications and mark-as-read
- Search for visible table records and page content
- AI Farm Assistant page
  - Local farm advisory mode works without an API key
  - Optional OpenAI-powered responses when OPENAI_API_KEY is configured
- Existing FarmPro pages and styling retained, with new AI assistant page

REQUIREMENTS
- Python 3.10 or newer
- pip

WINDOWS SETUP (VS CODE TERMINAL)
1. Extract FarmPro_Python_AI_Database.zip.
2. Open the FarmPro_Full_Project folder in VS Code.
3. Open Terminal > New Terminal.
4. Create a virtual environment:
   python -m venv .venv
5. Activate it:
   .venv\Scripts\activate
6. Install packages:
   python -m pip install -r requirements.txt
7. Start the application:
   python app.py
8. Open this address in your browser:
   http://127.0.0.1:5000

DEMO LOGIN
Email: admin@farmpro.local
Password: FarmPro@123

DATABASE
SQLite file: farmpro.db
The database is generated automatically in the project folder. Do not delete it if you want to retain your saved users and farm records. Data is stored locally on the computer running the app.

OPTIONAL GENERATIVE AI
The AI assistant works in local farm-advisory mode without any API key. For generative AI responses:
1. Set an OpenAI API key in your environment:
   Windows PowerShell:
   $env:OPENAI_API_KEY="your-api-key"
2. Optionally set the model:
   $env:OPENAI_MODEL="gpt-4o-mini"
3. Run python app.py again.
API usage may incur charges. Do not share your API key or commit it to source control.

IMPORTANT
- The local advisory mode provides general farming suggestions, not a confirmed diagnosis.
- For pesticide application, crop disease, or safety-critical decisions, consult a local agricultural expert and follow approved product labels.
- This is a local educational project. Before public deployment, set a strong FARMPRO_SECRET_KEY, enable HTTPS, add CSRF protection, configure secure session cookies, and use production hosting rather than Flask's development server.
