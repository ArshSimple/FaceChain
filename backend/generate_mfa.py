import pyotp
import qrcode
import os

def generate_qr_code(user_email):
    # 1. Generate a random Secret Key
    # IMPORTANT: In your real app, you MUST save this 'secret' to your database for this user.
    secret = pyotp.random_base32()
    
    print("-------------------------------------------------")
    print(f"SECRET KEY: {secret}") 
    print("(Save this key to your database user table!)")
    print("-------------------------------------------------")

    # 2. Create the Auth URI (Standard format for Google Auth / Authy)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user_email,
        issuer_name="FaceChain"  # Your App Name
    )

    # 3. Generate the QR Image
    img = qrcode.make(uri)
    
    # 4. Save the image
    file_name = "mfa_qrcode.png"
    img.save(file_name)
    print(f"QR Code successfully saved as '{file_name}'")
    print("Open this image and scan it with Google Authenticator.")
    
    return secret

# Run the function
if __name__ == "__main__":
    # You can change the email to test different users
    generate_qr_code("arsh@facechain.com")