\# 🚗 Carvion Motors



Carvion Motors is a web-based car marketplace platform built with \*\*Python Flask\*\*.  

The platform connects car sellers with potential buyers by allowing sellers to list vehicles and buyers to browse, search, and make inquiries.



\---



\## 📌 Project Overview



Carvion Motors aims to simplify vehicle buying and selling by providing:



\- Seller vehicle listings

\- Buyer car browsing

\- Advanced car search and filtering

\- Admin approval system

\- Seller dashboard

\- Buyer inquiries

\- Multi-image vehicle galleries



\---



\## ✨ Features



\### 👤 User Management

\- User registration and login

\- Role-based accounts:

&#x20; - Buyer

&#x20; - Seller

&#x20; - Admin



\### 🚘 Car Listings

\- Add vehicle listings

\- Upload vehicle images

\- View detailed car information

\- Manage seller listings

\- Admin approval before publishing



\### 🔍 Search \& Filtering

Users can search vehicles by:



\- Brand

\- Model

\- Price range

\- Year

\- Location

\- Fuel type

\- Transmission



\### 💬 Inquiry System

\- Buyers can send inquiries

\- Admin can review inquiries

\- Seller communication support



\### 🛠 Admin Dashboard

\- Manage users

\- Approve/reject vehicle listings

\- Review inquiries

\- Monitor platform activity



\---



\## 🏗️ Technology Stack



\### Backend

\- Python

\- Flask

\- Flask-SQLAlchemy

\- Flask-Login



\### Database

\- SQLite (development)



\### Frontend

\- HTML5

\- CSS3

\- JavaScript

\- Jinja2 Templates



\### Tools

\- Git

\- GitHub

\- Visual Studio Code



\---



\## 📂 Project Structure



```

Carvion motors/

│

├── app.py

├── config.py

├── models.py

├── extensions.py

├── create\_admin.py

├── requirements.txt

│

├── routes/

│   ├── auth.py

│   ├── cars.py

│   ├── admin.py

│   └── messages.py

│

├── templates/

│   ├── index.html

│   ├── cars.html

│   ├── dashboard.html

│   └── ...

│

├── static/

│   ├── css/

│   └── images/

│

└── migrations/

```



\---



\## ⚙️ Installation



\### 1. Clone repository



```bash

git clone https://github.com/YOUR\_USERNAME/carvion-motors.git

```



\### 2. Enter project folder



```bash

cd carvion-motors

```



\### 3. Create virtual environment



```bash

python -m venv .venv

```



\### 4. Activate environment



Windows:



```bash

.venv\\Scripts\\activate

```



\### 5. Install dependencies



```bash

pip install -r requirements.txt

```



\### 6. Run application



```bash

python app.py

```



Open:



```

http://127.0.0.1:5000

```



\---



\## 🔐 Environment Variables



Create a `.env` file:



```

SECRET\_KEY=your\_secret\_key

DATABASE\_URL=sqlite:///database.db

```



Do not upload `.env` to GitHub.



\---



\## 🚀 Future Improvements



\- M-PESA payment integration

\- Online vehicle booking deposits

\- Cloud image storage

\- PostgreSQL production database

\- Mobile application

\- AI vehicle recommendations

\- Live chat system



\---



\## 👨‍💻 Developer



\*\*Mark Kimaru\*\*



Carvion Motors - Online Vehicle Marketplace Platform



\---



\## 📄 License



This project is currently for educational and development purposes.

