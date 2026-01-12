from web3 import Web3
import json
import time

# --- CONFIGURATION ---
GANACHE_URL = "http://127.0.0.1:7545"
web3 = Web3(Web3.HTTPProvider(GANACHE_URL))

if not web3.is_connected():
    print("❌ CRITICAL ERROR: Could not connect to Ganache!")
    exit()
else:
    print("✅ Connected to Ethereum (Ganache)")

# Use Account 0 to send logs
ADMIN_ACCT = web3.eth.accounts[0]

class EthereumLedger:
    def __init__(self):
        print("🚀 Ledger Mode: Direct Transaction Storage (No Contract Needed)")

    def add_log(self, user_id, action, status, ip=""):
        try:
            log_data = {
                "user": str(user_id),
                "action": str(action),
                "status": str(status),
                "ip": str(ip),
                "timestamp": int(time.time())
            }
            
            json_data = json.dumps(log_data)
            hex_data = web3.to_hex(text=json_data)

            tx = {
                'to': ADMIN_ACCT,
                'from': ADMIN_ACCT,
                'value': 0,
                'gas': 100000,
                'gasPrice': web3.eth.gas_price,
                'nonce': web3.eth.get_transaction_count(ADMIN_ACCT),
                'data': hex_data 
            }

            tx_hash = web3.eth.send_transaction(tx)
            print(f"⛏️  Log Saved to Blockchain! Hash: {tx_hash.hex()[:10]}...")
            return tx_hash.hex()
        except Exception as e:
            print(f"❌ Ledger Write Error: {e}")
            return None

    def get_logs(self):
        try:
            logs = []
            latest_block = web3.eth.block_number
            for i in range(0, latest_block + 1):
                block = web3.eth.get_block(i, full_transactions=True)
                for tx in block.transactions:
                    if tx['input'] and tx['input'] != '0x':
                        try:
                            # Standardize hex input
                            raw_input = tx['input']
                            if isinstance(raw_input, bytes):
                                raw_input = raw_input.hex()
                            
                            decoded_text = web3.to_text(hexstr=raw_input)
                            
                            if '"user":' in decoded_text:
                                entry = json.loads(decoded_text)
                                logs.append({
                                    "user_id": entry.get("user"),
                                    "action": entry.get("action"),
                                    "status": entry.get("status"),
                                    "timestamp": entry.get("timestamp"),
                                    "hash_short": tx['hash'].hex()[:10] + "..."
                                })
                        except:
                            continue 
            
            logs.reverse()
            print(f"📡 SCAN COMPLETE: Found {len(logs)} logs.")
            return logs
        except Exception as e:
            print(f"❌ Ledger Read Error: {e}")
            return []

eth_ledger = EthereumLedger()