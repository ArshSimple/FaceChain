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
        self.local_logs = [] 
        
        self.w3 = Web3(Web3.HTTPProvider(GANACHE_URL, request_kwargs={'timeout': 60}))
        self.account = None
        self.contract = None
        
        if self.w3.is_connected():
            print("✅ Connected to Ethereum (Ganache)")
            self.account = self.w3.eth.accounts[0] # Admin Account
            self.setup_contract()
        else:
            print("❌ Blockchain Connection Failed. Is Ganache running?")

    def setup_contract(self):
        deploy_new = True # Assume we need a new contract unless proven otherwise

        # 1. Check if we have an existing address saved
        if os.path.exists(CONTRACT_ADDRESS_FILE):
            try:
                with open(CONTRACT_ADDRESS_FILE, 'r') as f:
                    address = f.read().strip()
                
                if Web3.is_address(address):
                    # --- THE FIX: Check if the contract actually exists on Ganache right now ---
                    contract_code = self.w3.eth.get_code(address)
                    
                    if len(contract_code) > 2: # If length > 2, it's not empty ('0x')
                        abi = self.compile_contract_abi()
                        if abi:
                            self.contract = self.w3.eth.contract(address=address, abi=abi)
                            print(f"🔗 Reconnected to Existing Contract: {address}")
                            deploy_new = False
                    else:
                        print("⚠️ Ganache was restarted. Old contract is gone. Preparing new deployment...")
            except Exception as e: 
                pass

        # 2. Deploy New if needed (Ganache restarted OR first run)
        if deploy_new:
            print("⚙️  Compiling & Deploying New Contract...")
            abi, bytecode = self.compile_contract_full()
            if not abi or not bytecode: return

            try:
                FaceAuth = self.w3.eth.contract(abi=abi, bytecode=bytecode)
                tx_hash = FaceAuth.constructor().transact({'from': self.account})
                tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                
                contract_address = tx_receipt.contractAddress
                self.contract = self.w3.eth.contract(address=contract_address, abi=abi)
                
                # Overwrite the old address with the new one
                with open(CONTRACT_ADDRESS_FILE, 'w') as f:
                    f.write(contract_address)
                    
                print(f"✅ New Contract Deployed at: {contract_address}")
                self.add_log("SYSTEM", "CONTRACT_DEPLOY", "SUCCESS", "127.0.0.1")
                
            except Exception as e:
                print(f"❌ Deployment Failed: {e}")

    def compile_contract_abi(self):
        abi, _ = self.compile_contract_full()
        return abi

    def compile_contract_full(self):
        try:
            with open(SOLIDITY_SOURCE_FILE, 'r') as f: source = f.read()
            target_version = '0.8.0'
            try: get_installed_solc_versions()
            except: install_solc(target_version)
            compiled_sol = compile_source(source, output_values=['abi', 'bin'], solc_version=target_version)
            contract_id, contract_interface = next(iter(compiled_sol.items()))
            return contract_interface['abi'], contract_interface['bin']
        except: return None, None

    # --- CORE METHODS ---

    def register_user(self, user_id, encoding):
        if not self.contract: return False
        try:
            encoding_int = [int(val * 1000000) for val in encoding]
            tx_hash = self.contract.functions.registerUser(str(user_id), encoding_int).transact({'from': self.account, 'gas': 3000000}) 
            self.w3.eth.wait_for_transaction_receipt(tx_hash)
            return True
        except Exception as e:
            print(f"⚠️ Blockchain Register Error: {e}")
            return False

    def verify_user(self, user_id, encoding):
        self.add_log(user_id, "FACE_VERIFY", "MATCH_FOUND", "127.0.0.1")

    def add_log(self, user_id, action, status, ip):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.local_logs.insert(0, {
            "user_id": user_id, "action": action, "status": status, "ip": ip, "timestamp": timestamp
        })

        if self.contract:
            try:
                tx_hash = self.contract.functions.addAuditLog(
                    str(user_id), action, status, ip, int(time.time())
                ).transact({'from': self.account, 'gas': 3000000}) 
                print(f"📝 Log Saved to Chain: {action} - {status}")
            except Exception as e: 
                print(f"⚠️ Chain Write Error: {e}")

    def get_logs(self):
        return self.local_logs

eth_ledger = EthLedger()