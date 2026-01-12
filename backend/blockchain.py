import hashlib
import json
import time
import os

LOG_FILE = 'auth_logs.json'

class Blockchain:
    def __init__(self):
        self.chain = []
        if os.path.exists(LOG_FILE):
            try:
                with open(LOG_FILE, 'r') as f: self.chain = json.load(f)
            except: self.create_genesis()
        else:
            self.create_genesis()

    def create_genesis(self):
        self.create_block(proof=100, previous_hash='0', log_data="Genesis Block")

    def create_block(self, proof, previous_hash, log_data):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'log_data': log_data,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        self.chain.append(block)
        with open(LOG_FILE, 'w') as f: json.dump(self.chain, f, indent=4)
        return block

    def add_log(self, user_id, action, status, ip):
        log_entry = {"user_id": user_id, "action": action, "status": status, "ip": ip}
        if not self.chain: self.create_genesis()
        last_block = self.chain[-1]
        proof = self.proof_of_work(last_block['proof'])
        return self.create_block(proof, self.hash(last_block), log_entry)

    @staticmethod
    def hash(block):
        encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(encoded).hexdigest()

    def proof_of_work(self, last_proof):
        proof = 0
        while not hashlib.sha256(f'{proof**2 - last_proof**2}'.encode()).hexdigest().startswith('0000'):
            proof += 1
        return proof

ledger = Blockchain()