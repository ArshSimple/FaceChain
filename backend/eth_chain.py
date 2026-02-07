from web3 import Web3
from solcx import compile_source, install_solc, get_installed_solc_versions
import os
import json
import time
from datetime import datetime

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTRACTS_DIR = os.path.join(BASE_DIR, "contracts")

CONTRACT_ADDRESS_FILE = os.path.join(CONTRACTS_DIR, "contract_address.txt")
SOLIDITY_SOURCE_FILE = os.path.join(CONTRACTS_DIR, "FaceAuth.sol")

GANACHE_URL = "http://127.0.0.1:7545" 

class EthLedger:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(GANACHE_URL))
        self.account = None
        self.contract = None
        
        if self.w3.is_connected():
            print("✅ Connected to Ethereum (Ganache)")
            self.account = self.w3.eth.accounts[0] # Admin Account
            self.setup_contract()
        else:
            print("❌ Blockchain Connection Failed. Is Ganache running?")

    def setup_contract(self):
        # 1. Check if we have an existing address
        if os.path.exists(CONTRACT_ADDRESS_FILE):
            try:
                with open(CONTRACT_ADDRESS_FILE, 'r') as f:
                    address = f.read().strip()
                
                if not Web3.is_address(address): raise ValueError("Invalid address")

                abi = self.compile_contract_abi()
                if abi:
                    self.contract = self.w3.eth.contract(address=address, abi=abi)
                    print(f"🔗 Connected to Smart Contract: {address}")
                    return
            except Exception as e:
                print(f"⚠️ Contract Load Error: {e}")

        # 2. Deploy New if needed
        print("⚙️  Compiling & Deploying New Contract...")
        abi, bytecode = self.compile_contract_full()
        if not abi or not bytecode: return

        try:
            FaceAuth = self.w3.eth.contract(abi=abi, bytecode=bytecode)
            tx_hash = FaceAuth.constructor().transact({'from': self.account})
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            contract_address = tx_receipt.contractAddress
            self.contract = self.w3.eth.contract(address=contract_address, abi=abi)
            
            with open(CONTRACT_ADDRESS_FILE, 'w') as f:
                f.write(contract_address)
                
            print(f"✅ New Contract Deployed at: {contract_address}")
            
            # Add a startup log
            self.add_log("SYSTEM", "CONTRACT_DEPLOY", "SUCCESS", "127.0.0.1")
            
        except Exception as e:
            print(f"❌ Deployment Failed: {e}")

    def compile_contract_abi(self):
        abi, _ = self.compile_contract_full()
        return abi

    def compile_contract_full(self):
        try:
            with open(SOLIDITY_SOURCE_FILE, 'r') as f:
                source = f.read()
            
            target_version = '0.8.0'
            installed_versions = [str(v) for v in get_installed_solc_versions()]
            if target_version not in installed_versions:
                install_solc(target_version)
            
            compiled_sol = compile_source(
                source, output_values=['abi', 'bin'], solc_version=target_version
            )
            contract_id, contract_interface = next(iter(compiled_sol.items()))
            return contract_interface['abi'], contract_interface['bin']
        except Exception as e:
            print(f"❌ Solc Error: {e}")
            return None, None

    # --- PUBLIC METHODS ---

    def register_user(self, user_id, encoding):
        if not self.contract: return False
        try:
            # Convert float array to int array for solidity
            encoding_int = [int(val * 1000000) for val in encoding]
            tx_hash = self.contract.functions.registerUser(
                str(user_id), encoding_int
            ).transact({'from': self.account})
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            return True
        except Exception as e:
            print(f"⚠️ Blockchain Register Error: {e}")
            return False

    def verify_user(self, user_id, encoding):
        # Optional: On-chain verification logic could go here
        # For now, we just log the successful verification event
        self.add_log(user_id, "FACE_VERIFY", "MATCH_FOUND", "127.0.0.1")

    def add_log(self, user_id, action, status, ip):
        if not self.contract: return
        try:
            self.contract.functions.addAuditLog(
                str(user_id), action, status, ip, int(time.time())
            ).transact({'from': self.account})
            print(f"📝 Log Added: {action} - {status}")
        except Exception as e: 
            print(f"⚠️ Logging Failed: {e}")

    def get_logs(self):
        if not self.contract: return []
        try:
            logs = self.contract.functions.getAuditLogs().call()
            formatted = []
            for l in reversed(logs):
                formatted.append({
                    "user_id": l[0],
                    "action": l[1],
                    "status": l[2],
                    "ip": l[3],
                    "timestamp": datetime.fromtimestamp(int(l[4])).strftime('%H:%M:%S')
                })
            return formatted
        except Exception as e:
            print(f"⚠️ Fetch Logs Error: {e}")
            return []

eth_ledger = EthLedger()