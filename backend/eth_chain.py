from web3 import Web3
from solcx import compile_standard, install_solc
import json
import os
import time

# --- CONFIGURATION ---
GANACHE_URL = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

if not web3.is_connected():
    print("❌ CRITICAL ERROR: Could not connect to Ganache!")
    exit()
else:
    print("✅ Connected to Ethereum (Ganache)")

ADMIN_ACCT = web3.eth.accounts[0]
web3.eth.default_account = ADMIN_ACCT

# --- SOLIDITY SOURCE CODE ---
SOLIDITY_SOURCE = '''
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract FaceAuth {
    struct UserProfile {
        string userId;
        int256[] faceEmbedding; 
        bool exists;
    }
    
    mapping(string => UserProfile) private users;
    
    event UserRegistered(string userId, uint256 timestamp);
    event AuthAttempt(string userId, bool success, int256 distance, uint256 timestamp);
    event AdminAction(string userId, string action, string status, uint256 timestamp);

    function registerUser(string memory _id, int256[] memory _embedding) public {
        require(_embedding.length == 128, "Invalid Face Data length");
        users[_id] = UserProfile(_id, _embedding, true);
        emit UserRegistered(_id, block.timestamp);
    }

    function verifyUser(string memory _id, int256[] memory _inputEmbedding) public returns (bool) {
        require(users[_id].exists, "User not found on chain");
        require(_inputEmbedding.length == 128, "Invalid Input Data length");

        int256 storedDistance = 0;
        int256[] memory storedFace = users[_id].faceEmbedding;

        for (uint i = 0; i < 128; i++) {
            int256 diff = storedFace[i] - _inputEmbedding[i];
            storedDistance += diff * diff; 
        }

        // Threshold: 0.6 distance ~ 36,000,000 (scaled by 10000^2)
        bool isMatch = storedDistance < 45000000; 
        
        emit AuthAttempt(_id, isMatch, storedDistance, block.timestamp);
        return isMatch;
    }

    function addLog(string memory _user, string memory _action, string memory _status) public {
        emit AdminAction(_user, _action, _status, block.timestamp);
    }
}
'''

class EthereumLedger:
    def __init__(self):
        self.address_file = "contract_address.txt"
        self.contract = None
        self.init_contract()

    def compile_source(self):
        print("⚙️  Compiling Solidity Code...")
        try:
            # Install specific solc version if missing
            install_solc('0.8.0')
            
            compiled_sol = compile_standard({
                "language": "Solidity",
                "sources": {"FaceAuth.sol": {"content": SOLIDITY_SOURCE}},
                "settings": {"outputSelection": {"*": {"*": ["abi", "metadata", "evm.bytecode", "evm.sourceMap"]}}}
            }, solc_version='0.8.0')
            
            bytecode = compiled_sol['contracts']['FaceAuth.sol']['FaceAuth']['evm']['bytecode']['object']
            abi = json.loads(compiled_sol['contracts']['FaceAuth.sol']['FaceAuth']['metadata'])['output']['abi']
            return abi, bytecode
        except Exception as e:
            print(f"❌ COMPILATION FAILED: {e}")
            return None, None

    def init_contract(self):
        # 1. Always compile to get fresh ABI/Bytecode
        self.abi, self.bytecode = self.compile_source()
        if not self.abi or not self.bytecode: return

        # 2. Check for existing deployment
        if os.path.exists(self.address_file):
            with open(self.address_file, "r") as f:
                addr = f.read().strip()
            if web3.is_address(addr):
                self.contract = web3.eth.contract(address=addr, abi=self.abi)
                print(f"🔗 Connected to Smart Contract: {addr}")
                return

        # 3. If no file, Deploy new
        self.deploy_contract()

    def deploy_contract(self):
        print("⚡ Deploying Verification Smart Contract...")
        try:
            FaceAuth = web3.eth.contract(abi=self.abi, bytecode=self.bytecode)
            tx_hash = FaceAuth.constructor().transact({'from': ADMIN_ACCT})
            tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
            
            addr = tx_receipt.contractAddress
            with open(self.address_file, "w") as f:
                f.write(addr)
            
            self.contract = web3.eth.contract(address=addr, abi=self.abi)
            print(f"🚀 Contract Deployed Successfully: {addr}")
        except Exception as e:
            print(f"❌ DEPLOYMENT FAILED: {e}")

    # Helper: Convert Float Embeddings to Integers
    def prepare_embedding(self, embedding):
        return [int(x * 10000) for x in embedding]

    def register_user(self, user_id, embedding):
        if not self.contract: return False
        try:
            int_embedding = self.prepare_embedding(embedding)
            # INCREASED GAS TO 6,000,000
            tx_hash = self.contract.functions.registerUser(str(user_id), int_embedding).transact({'from': ADMIN_ACCT, 'gas': 6000000})
            web3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"⛏️  User {user_id} Registered on Blockchain!")
            return True
        except Exception as e:
            print(f"❌ Register Error: {e}")
            return False

    def verify_user(self, user_id, live_embedding):
        if not self.contract: return False
        try:
            int_embedding = self.prepare_embedding(live_embedding)
            # INCREASED GAS TO 6,000,000
            tx_hash = self.contract.functions.verifyUser(str(user_id), int_embedding).transact({'from': ADMIN_ACCT, 'gas': 6000000})
            web3.eth.wait_for_transaction_receipt(tx_hash)
            print(f"⛏️  Verification Computed on Blockchain.")
            return True
        except Exception as e:
            print(f"❌ On-Chain Verify Failed: {e}")
            return False

    def add_log(self, user_id, action, status, ip=""):
        if not self.contract: return None
        try:
            tx_hash = self.contract.functions.addLog(str(user_id), f"{action} ({ip})", str(status)).transact({'from': ADMIN_ACCT, 'gas': 600000})
            return tx_hash.hex()
        except Exception as e:
            print(f"❌ Log Error: {e}")
            return None

    def get_logs(self):
        if not self.contract: return []
        try:
            logs = []
            # Fetch generic admin logs
            events = self.contract.events.AdminAction.get_logs(from_block=0)
            for e in events:
                logs.append({
                    "user_id": e.args.userId,
                    "action": e.args.action,
                    "status": e.args.status,
                    "timestamp": e.args.timestamp,
                    "hash_short": e.transactionHash.hex()[:10] + "..."
                })
            
            # Fetch verification attempts
            attempts = self.contract.events.AuthAttempt.get_logs(from_block=0)
            for e in attempts:
                status = "SUCCESS" if e.args.success else "FAILED"
                logs.append({
                    "user_id": e.args.userId,
                    "action": "ON-CHAIN VERIFY",
                    "status": status,
                    "timestamp": e.args.timestamp,
                    "hash_short": e.transactionHash.hex()[:10] + "..."
                })
                
            logs.sort(key=lambda x: x['timestamp'], reverse=True)
            return logs
        except Exception as e:
            print(f"❌ Read Error: {e}")
            return []

eth_ledger = EthereumLedger()