import asyncio
import discord
from discord.ext import commands, tasks
import datetime
from collections import defaultdict

import google.generativeai as genai
import os

BOT_TOKEN = "*"
GEMINI_API_KEY = "*"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

# Set up Bot with command prefix and required intents
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # REQUIRED for receiving message content
bot = commands.Bot(command_prefix="!", intents=intents)

# Reminders storage: mapping user IDs to a list of reminder dicts
reminders = defaultdict(list)
global_reminder_id = 1  # Global counter to assign unique IDs to reminders

# Print when bot is online and start the reminder checker
@bot.event
async def on_ready():
    print(f"✅ Bot is online! Logged in as {bot.user}")
    reminder_checker.start()

# Process messages: If it's a command, let the command handler work.
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Process commands normally if message starts with the command prefix
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    print(f"📩 Received message: {message.content}")  # Debugging output

    user_input = message.content.strip()
    if not user_input:
        return

    try:
        response = model.generate_content(user_input)  # Get response from Gemini
        if response.text.strip():
            await message.channel.send(response.text)
        else:
            await message.channel.send("⚠ Sorry, I couldn't generate a response.")
    except Exception as e:
        print(f"❌ Error in on_message: {e}")
        await message.channel.send("⚠ An error occurred while processing your request.")

#Command: Chat (explicitly use Gemini API)
@bot.command()
async def chat(ctx, *, message: str):
    try:
        response = model.generate_content(message)
        if response.text.strip():
            await ctx.send(response.text)
        else:
            await ctx.send("⚠ Sorry, I couldn't generate a response.")
    except Exception as e:
        print(f"❌ Error in chat command: {e}")
        await ctx.send("⚠ An error occurred while processing your request.")

# Command: Create a reminder
@bot.command()
async def remind(ctx, time: str, *, reminder: str):
    try:
        reminder_time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
        global global_reminder_id
        reminder_entry = {"id": global_reminder_id, "time": reminder_time, "text": reminder}
        reminders[ctx.author.id].append(reminder_entry)
        await ctx.send(f"Reminder set (ID: {global_reminder_id}) for {time}: {reminder}")
        global_reminder_id += 1
    except ValueError:
        await ctx.send("Invalid time format! Use YYYY-MM-DD HH:MM")

# Command: List your reminders
@bot.command()
async def reminders_list(ctx):
    user_reminders = reminders.get(ctx.author.id, [])
    if not user_reminders:
        await ctx.send("You have no reminders set.")
        return
    message_lines = ["Your reminders:"]
    for r in user_reminders:
        message_lines.append(f"ID {r['id']}: {r['time'].strftime('%Y-%m-%d %H:%M')} - {r['text']}")
    await ctx.send("\n".join(message_lines))

# Command: Delete a reminder by its ID
@bot.command()
async def delete_reminder(ctx, reminder_id: int):
    user_reminders = reminders.get(ctx.author.id, [])
    for r in user_reminders:
        if r["id"] == reminder_id:
            user_reminders.remove(r)
            await ctx.send(f"Deleted reminder with ID {reminder_id}.")
            return
    await ctx.send(f"No reminder found with ID {reminder_id}.")

# Command: Modify a reminder
@bot.command()
async def modify_reminder(ctx, reminder_id: int, time: str, *, reminder: str):
    try:
        new_time = datetime.datetime.strptime(time, "%Y-%m-%d %H:%M")
    except ValueError:
        await ctx.send("Invalid time format! Use YYYY-MM-DD HH:MM")
        return

    user_reminders = reminders.get(ctx.author.id, [])
    for r in user_reminders:
        if r["id"] == reminder_id:
            r["time"] = new_time
            r["text"] = reminder
            await ctx.send(f"Modified reminder with ID {reminder_id} to {time}: {reminder}")
            return
    await ctx.send(f"No reminder found with ID {reminder_id}.")

# Background task: Check reminders every minute and send DM when time arrives
@tasks.loop(minutes=1)
async def reminder_checker():
    now = datetime.datetime.now()
    print(f"[DEBUG] Checking reminders at: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    for user_id, user_reminders in list(reminders.items()):
        for r in list(user_reminders):
            print(f"[DEBUG] Reminder {r['id']} scheduled for {r['time']} - {r['text']}")
            if now >= r["time"]:
                print(f"[DEBUG] Reminder {r['id']} is due!")
                user = bot.get_user(user_id)
                if user is None:
                    try:
                        user = await bot.fetch_user(user_id)
                        print(f"[DEBUG] Fetched user: {user}")
                    except Exception as e:
                        print(f"[ERROR] Could not fetch user with ID {user_id}: {e}")
                        continue
                try:
                    await user.send(f"Reminder: {r['text']}")
                    print(f"[DEBUG] Sent reminder to {user}")
                except Exception as e:
                    print(f"[ERROR] Error sending reminder DM: {e}")
                user_reminders.remove(r)
        if not user_reminders:
            del reminders[user_id]

# Command: Create a Poll
# Usage: !poll "Question" Option1 Option2 Option3 ...
@bot.command()
async def poll(ctx, question: str, *options):
    if len(options) < 2:
        await ctx.send("You need at least two options for a poll.")
        return

    reactions = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    poll_message = f"**{question}**\n"
    for i, option in enumerate(options):
        poll_message += f"{reactions[i]} {option}\n"

    message = await ctx.send(poll_message)
    for i in range(len(options)):
        await message.add_reaction(reactions[i])

# Run the bot
bot.run(BOT_TOKEN)
