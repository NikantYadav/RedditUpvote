# RedditUpvote – Beginner-Friendly Guide

Welcome to **RedditUpvote**, a simple tool that helps you automate upvoting posts on Reddit using multiple accounts. This guide is designed for absolute beginners, so don't worry if you're new to programming or automation. We'll walk you through each step with clear instructions and helpful visuals.

---

## 📋 What You’ll Need

Before we begin, make sure you have:

* **A Windows PC** (this guide is tailored for Windows users)
* **Python 3.11.3** installed on your computer
* **Internet access** to download necessary files
* **Reddit accounts** that you want to use for upvoting

---

## 🛠️ Step-by-Step Setup

### 1. Clone the Repository

This means copying the project files to your computer.

1. Open **PowerShell** (a program on your computer).
2. Type the following command and press Enter:

   ```powershell
   git clone https://github.com/NikantYadav/RedditUpvote.git
   cd RedditUpvote
   ```

> *If you don't have Git installed, google how to install it.*

---

### 2. Create `account_state.json`

In PowerShell, run this command:

```powershell
New-Item account_state.json -ItemType File
```

This creates an empty file where your account data will be stored.

> ⚠️ Make sure you're inside the `RedditUpvote` folder when you run this.

---

### 3. Create `profiles` Folder

Now create a folder to store Reddit session data:

```powershell
New-Item -ItemType Directory -Name profiles
```

This folder will hold login information for each account after they’re added.

---

### 4. Create a Virtual Environment

This step sets up a clean workspace for the project.

In PowerShell, type:

```powershell
python -m venv env
```

Then activate the virtual environment:

```powershell
.\env\Scripts\activate
```

---

### 5. Install Required Packages

This installs the necessary tools for the project.

In PowerShell, type:

```powershell
pip install -r requirements.txt
```

---

## 👤 Adding Reddit Accounts

Now, let's add your Reddit accounts to the tool.

1. In PowerShell, type:

   ```powershell
   python account_gui.py
   ```

> *The first time you run the program, it may take some time as additional packages are installed.*

2. A window will open.

3. Click **"Add Account"** and enter:

   * **Account ID**
   * **Proxy details** (if you have them)
   * **Username**

4. The tool will open Reddit, log in, browse posts, scroll a little, and then close the window.

5. Click **"Exit & Save"** to save the account details.

> *Repeat this process for each Reddit account you want to add.*

---

## 🎯 Running the Bot

After adding accounts, set up where you want the bot to upvote.

1. In PowerShell, type:

   ```powershell
   python target_gui.py
   ```

2. A window will open. Click on **"New Instance"**.

3. A new window will open for you to configure the target.

4. Enter the specific post URL you want to target.

5. Adjust any settings as needed.

6. Click on **"Start Upvoting"**.

The bot will begin the upvoting process:

* Multiple Reddit windows will open, each corresponding to a Reddit account you've configured.
* Each account will log in, navigate to the specified post, and perform the upvote.
* After completing the upvote, each window will close automatically.

---

## 📝 Notes

* **First-Time Setup**: The first time you run `account_gui.py`, it may take some time as additional packages are installed.
* **Proxy Details**: If you don't have proxy details, you can leave them blank.
* **Reddit Interaction**: The bot simulates human-like interactions by opening Reddit, logging in, browsing posts, scrolling a little, and then closing the window.

---

If you have any questions or need further assistance, feel free to reach out. Happy automating!
