# test_viral_story.py
import edge_tts
import asyncio
import os

async def generate_speech(text, voice, output_file, rate="+12%"):
    print(f"🎤 Generating with {voice} at {rate} speed...")
    
    communicate = edge_tts.Communicate(text, voice, rate=rate)
    await communicate.save(output_file)
    
    print(f"✅ Generated: {output_file}")

def play_audio(file_path):
    abs_path = os.path.abspath(file_path)
    print(f"🔊 Playing: {abs_path}")
    os.startfile(abs_path)

async def main():
    
    nuclear_story = """I found out my husband was cheating through our Ring doorbell.
I was at work when I got a motion alert at 2 PM on a Tuesday.
Opened the app expecting a package delivery. Instead, I saw him walking in with a woman.
The same husband who told me he had back to back meetings all day.
I watched them walk into my house. The house I paid the down payment on.
I called my best friend. Told her to go check. She has a spare key.
Twenty minutes later, she sent me a photo. They were in our bed.
I didn't cry. I didn't scream. I got strategic.
First, I called my lawyer. Started divorce paperwork immediately.
Then I changed every lock in the house. Had a locksmith there within an hour.
Moved all his stuff to his mom's driveway. She wasn't home, didn't matter.
Changed the Ring password so he couldn't delete the evidence.
Downloaded the footage. Backed it up three times. Sent copies to my lawyer.
At 6 PM, he comes home like nothing happened. His key doesn't work.
I'm watching him on the Ring app from my car parked down the street.
He tries the key five times. Checks his phone. Tries again.
Finally, he calls me. I let it ring twice, then answer on speaker.
He says, babe, something's wrong with the lock. Can you come home?
I said, nothing's wrong with the lock. I changed it.
Dead silence. Then, wait, what? Why would you do that?
I said, check your email. Sent you something interesting.
I hear him opening his phone. Then I hear him panic.
He starts yelling. Saying I'm crazy. That I'm overreacting.
I said, your mom has your clothes. My lawyer has the footage. We're done.
He's begging now. Saying she meant nothing. That he made a mistake.
I said, the mistake was thinking I wouldn't find out. Goodbye.
And I hung up. Blocked his number. Blocked him everywhere.
Next morning, he shows up at my office with flowers. Crying in the lobby.
Security escorted him out. My boss saw everything. She gave me the day off.
Two days later, his mom calls me. Apologizing. Said she raised him better.
I told her I appreciated that, but this wasn't her fault.
A week later, the woman reached out on Instagram. Said she didn't know he was married.
I sent her the wedding photos. She blocked him too.
My divorce was finalized in three months. I got the house, the car, and half his retirement.
He had to pay my legal fees too.
Last I heard, he's living in a studio apartment, still trying to get back on dating apps.
Me? I'm thriving. Took a solo trip to Italy. Started my own business.
Best revenge is living well.
And changing the locks."""
    
    voice = "en-US-JennyNeural"
    output_file = "nuclear_story.mp3"
    
    print("=" * 60)
    print("🔥 NUCLEAR REDDIT STORY - FULL SAGA")
    print("=" * 60)
    print()
    
    await generate_speech(nuclear_story, voice, output_file, rate="+12%")
    
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        print(f"📊 Size: {file_size:,} bytes")
        
        print()
        play_audio(output_file)
        
        print("\n✅ NOW we're talking")
        print("🔥 Multiple plot points")
        print("⚖️ Lawyer, divorce, legal fees")
        print("💰 House, car, retirement")
        print("🌍 Italy trip, new business")
        print("👑 FULL revenge arc")

if __name__ == "__main__":
    asyncio.run(main())