# 🛡️ FaceChain: Blockchain-Based AI Authentication System

![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/framework-Flask-lightgrey.svg)
![Blockchain](https://img.shields.io/badge/blockchain-Ethereum%20%7C%20Ganache-purple.svg)
![AI](https://img.shields.io/badge/AI-ResNet--34%20%7C%20OpenCV-green.svg)

**FaceChain** is a decentralized, privacy-first authentication portal designed for secure online examinations and digital environments. It eliminates the vulnerabilities of centralized databases (Single Point of Failure) and proxy attendance by merging Artificial Intelligence (Facial Recognition) with the immutability of Blockchain Technology.

Developed as a Final Year Project for **B.Voc. Web Technology** at K.C. College, Mumbai.

---

## 🚀 Key Features

* **Privacy-Preserving Biometrics:** Uses a pre-trained ResNet-34 model to convert facial features into 128-dimensional mathematical vectors. Raw photographs are **never** stored.
* **Immutable Audit Trail:** All access logs (Success/Fail) are anchored to an Ethereum Smart Contract. Once logged, records cannot be altered or deleted, even by administrators.
* **Defense-in-Depth (MFA):** Integrates Time-Based One-Time Passwords (TOTP) via Google Authenticator to thwart photographic replay and spoofing attacks.
* **Dual-Timer Proctoring Engine:** Actively monitors the user's presence during exams—checking locally every 1 second for instant UI feedback, while throttling blockchain writes to every 30 seconds to prevent network congestion.
* **Admin SOC Dashboard:** A real-time Security Operations Center to manage exam schedules and monitor decentralized audit logs directly from the Ganache testnet.

---

## 🛠️ Technology Stack

**Frontend:**
* HTML5, CSS3, JavaScript (ES6)
* Webcam API (`navigator.mediaDevices`)

**Backend & AI:**
* **Framework:** Python Flask (`app.py`)
* **Computer Vision:** OpenCV (`cv2`)
* **Deep Learning:** `dlib`, `face_recognition` 
* **Security:** `pyotp` (Google Authenticator MFA)

**Blockchain Layer:**
* **Network:** Ganache (Local Ethereum Testnet)
* **Smart Contracts:** Solidity (`FaceAuth.sol`)
* **Integration:** `web3.py` (`eth_chain.py`)

---

## ⚙️ Prerequisites

Before you begin, ensure you have the following installed on your system:
1. **Python 3.10** or higher
2. **Ganache** (UI or CLI) for local blockchain simulation
3. **C++ Build Tools** (Required for installing `dlib` on Windows)
4. A working **Webcam**

---

## 💻 Installation & Setup

**1. Clone the Repository**
```bash
git clone [https://github.com/ArshSimple/FaceChain.git](https://github.com/ArshSimple/FaceChain.git)
cd FaceChain
````

**2. Install Python Dependencies**
Install the required packages using the provided requirements file:

```bash
pip install -r requirements.txt
```

**3. Setup the Blockchain (Ganache)**

  * Open **Ganache** and start a new Quickstart workspace.
  * Open Remix IDE (https://www.google.com/search?q=https://remix.ethereum.org) or use Truffle/Hardhat to compile and deploy `FaceAuth.sol` to your Ganache network.
  * Copy the deployed **Contract Address** and paste it into `contract_address.txt`.
  * Ensure the RPC Server in `eth_chain.py` matches your Ganache instance (usually `http://127.0.0.1:7545`).

**4. Run the Application**
You can start the project using the provided batch file or via Python:

```bash
# Using batch file (Windows)
start_project.bat

# OR using Python directly
python app.py
```

*The system will be accessible at `http://127.0.0.1:5000`*

-----

## 📖 How to Use

1.  **Registration:** Navigate to the "New Student" portal. Enter your Roll No. and Name. Allow webcam access to capture your face vector.
2.  **MFA Setup:** Scan the generated QR code using the **Google Authenticator** app on your smartphone.
3.  **Authentication:** Go to "Student Login". Scan your face. If a \>90% match is found, enter the 6-digit OTP from your phone.
4.  **Proctored Exam:** Once authenticated, the exam portal will monitor your presence. If you leave the frame, a 120-second warning timer initiates before session termination.
5.  **Admin Auditing:** Log into the Admin Dashboard to view the immutable ledger of all access attempts fetched securely from the blockchain.

-----

## 📁 Core Project Structure

```text
FaceChain/
│
├── app.py                  # Main Flask application and routing
├── face_utils.py           # AI logic (128D vector extraction & matching)
├── eth_chain.py            # Web3.py integration for Ganache
├── FaceAuth.sol            # Solidity Smart Contract for audit logs
├── contract_address.txt    # Stores the deployed contract address
├── requirements.txt        # Python dependencies
├── start_project.bat       # Windows execution script
│
├── /templates              # Frontend UI files
│   ├── index.html          # Landing & Login page
│   └── admin_dashboard.html# SOC Dashboard
│
└── /data                   # Local JSON storage
    ├── known_embeddings.json # Encrypted face vectors
    └── exam_schedule.json    # Exam scheduling constraints
```

-----

## 👥 Authors

  * **Arsh Agrawal** - *Core Backend, Blockchain Integration & AI*
  * **Kaizad Bharucha** - *Frontend Development & UI/UX*

**Under the esteemed guidance of:** Mr. Sadiq Batliwala  
**Department:** B.Voc. Web Technology, K.C. College, Mumbai

-----

*FaceChain - Replacing Blind Trust with Unbreakable Code.*

```