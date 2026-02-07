// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract FaceAuth {
    struct User {
        string userId;
        bytes32 faceEncodingHash;
        bool isRegistered;
        uint256 regTimestamp;
    }

    // New: Audit Log Structure
    struct Log {
        string userId;
        string action;
        string status;
        string ip;
        uint256 timestamp;
    }

    mapping(string => User) public users;
    Log[] public auditLogs; // Stores history
    address public admin;

    event UserRegistered(string userId, uint256 timestamp);
    event AccessLogged(string userId, string action, string status, uint256 timestamp);

    constructor() {
        admin = msg.sender;
    }

    // Register User (Modified to handle int array input from Python)
    function registerUser(string memory _userId, int256[] memory _encoding) public {
        // We create a hash of the encoding to save gas
        bytes32 hash = keccak256(abi.encodePacked(_encoding));
        
        users[_userId] = User(_userId, hash, true, block.timestamp);
        emit UserRegistered(_userId, block.timestamp);
    }

    // New: Add Audit Log
    function addAuditLog(string memory _userId, string memory _action, string memory _status, string memory _ip, uint256 _timestamp) public {
        auditLogs.push(Log(_userId, _action, _status, _ip, _timestamp));
        emit AccessLogged(_userId, _action, _status, _timestamp);
    }

    // New: Fetch All Logs
    function getAuditLogs() public view returns (Log[] memory) {
        return auditLogs;
    }
}