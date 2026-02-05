// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract FaceAuth {
    
    struct UserProfile {
        string userId;
        int256[] faceEmbedding; // Storing 128 numbers as integers
        bool exists;
    }
    
    mapping(string => UserProfile) private users;
    
    // Event to log the result
    event AuthAttempt(string userId, bool success, int256 distance);

    // 1. REGISTER: Store the face vector (multiplied by 10000)
    function registerUser(string memory _id, int256[] memory _embedding) public {
        require(_embedding.length == 128, "Invalid Face Data");
        users[_id] = UserProfile(_id, _embedding, true);
    }

    // 2. VERIFY: Compare input face with stored face ON-CHAIN
    function verifyUser(string memory _id, int256[] memory _inputEmbedding) public returns (bool) {
        require(users[_id].exists, "User not found");
        require(_inputEmbedding.length == 128, "Invalid Input Data");

        int256 storedDistance = 0;
        int256[] memory storedFace = users[_id].faceEmbedding;

        // Euclidean Distance Calculation Loop
        for (uint i = 0; i < 128; i++) {
            int256 diff = storedFace[i] - _inputEmbedding[i];
            storedDistance += diff * diff; // Square the difference
        }

        // Threshold (0.6 * 10000)^2 = 36,000,000 (roughly)
        // You will need to tune this integer threshold based on your scaling
        bool isMatch = storedDistance < 40000000; 
        
        emit AuthAttempt(_id, isMatch, storedDistance);
        return isMatch;
    }
}