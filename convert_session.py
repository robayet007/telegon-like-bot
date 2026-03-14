"""
Script to convert Telethon session file to StringSession for Vercel deployment
Run this locally to get your SESSION_STRING for Vercel environment variables
"""
import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

async def convert_session():
    """Convert file session to string session"""
    print("🔄 Converting session file to StringSession...")
    
    try:
        # Load existing file session
        file_client = TelegramClient('ff_like_bot', API_ID, API_HASH)
        await file_client.start()
        
        # Check if authorized
        if not await file_client.is_user_authorized():
            print("❌ Error: Session is not authorized. Please run bot.py first to authenticate.")
            await file_client.disconnect()
            return
        
        # Get user info to verify
        me = await file_client.get_me()
        print(f"✅ Connected as: {me.first_name} (@{me.username or 'N/A'})")
        
        # Method 1: Direct conversion using session data
        session_obj = file_client.session
        
        # Create StringSession and manually set the auth key and DC
        string_session = StringSession()
        
        # Copy auth key and DC info
        if hasattr(session_obj, 'auth_key') and session_obj.auth_key:
            string_session.auth_key = session_obj.auth_key
        
        if hasattr(session_obj, 'dc_id'):
            string_session.set_dc(
                session_obj.dc_id,
                session_obj.server_address,
                session_obj.port
            )
        
        # Get the string representation
        session_string = string_session.save()
        
        # If that didn't work, try method 2: Create new client with StringSession
        if not session_string or len(session_string) < 10:
            print("⚠️  Trying alternative conversion method...")
            
            # Create a temporary StringSession
            temp_session = StringSession()
            temp_client = TelegramClient(temp_session, API_ID, API_HASH)
            
            # Manually set the session data before connecting
            if hasattr(session_obj, 'auth_key') and session_obj.auth_key:
                temp_session.auth_key = session_obj.auth_key
            if hasattr(session_obj, 'dc_id'):
                temp_session.set_dc(
                    session_obj.dc_id,
                    session_obj.server_address,
                    session_obj.port
                )
            
            # Now get the string
            session_string = temp_session.save()
            await temp_client.disconnect()
        
        # Final check
        if not session_string or len(session_string) < 10:
            print("❌ Error: Could not generate valid session string.")
            print("💡 Tip: Make sure your session file is valid and you're logged in.")
            await file_client.disconnect()
            return
        
        print("\n✅ Session converted successfully!")
        print("\n" + "="*70)
        print("Copy this SESSION_STRING to your Vercel environment variables:")
        print("="*70)
        print(session_string)
        print("="*70)
        print(f"\n📏 Length: {len(session_string)} characters")
        print("\n📝 Add this to Vercel Environment Variables:")
        print(f"SESSION_STRING={session_string}")
        print("\n⚠️  Keep this secret! Don't share it publicly.")
        print("✅ You can now use this in your Vercel deployment.")
        
        await file_client.disconnect()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(convert_session())
