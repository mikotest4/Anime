import urllib.parse
from asyncio import sleep as asleep, gather
from pyrogram.filters import command, private, user
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait, MessageNotModified

from bot import bot, bot_loop, Var, ani_cache
from bot.core.database import db
from bot.core.func_utils import decode, is_fsubbed, get_fsubs, editMessage, sendMessage, new_task, convertTime, getfeed
from bot.core.auto_animes import get_animes
from bot.core.reporter import rep

@bot.on_message(command('start') & private)
@new_task
async def start_msg(client, message):
    uid = message.from_user.id
    from_user = message.from_user
    txtargs = message.text.split()
    temp = await sendMessage(message, "<i>Connecting..</i>")
    if not await is_fsubbed(uid):
        txt, btns = await get_fsubs(uid, txtargs)
        return await editMessage(temp, txt, InlineKeyboardMarkup(btns))
    if len(txtargs) <= 1:
        await temp.delete()
        btns = []
        for elem in Var.START_BUTTONS.split():
            try:
                bt, link = elem.split('|', maxsplit=1)
            except:
                continue
            if len(btns) != 0 and len(btns[-1]) == 1:
                btns[-1].insert(1, InlineKeyboardButton(bt, url=link))
            else:
                btns.append([InlineKeyboardButton(bt, url=link)])
        smsg = Var.START_MSG.format(first_name=from_user.first_name,
                                    last_name=from_user.first_name,
                                    mention=from_user.mention, 
                                    user_id=from_user.id)
        if Var.START_PHOTO:
            await message.reply_photo(
                photo=Var.START_PHOTO, 
                caption=smsg,
                reply_markup=InlineKeyboardMarkup(btns) if len(btns) != 0 else None
            )
        else:
            await sendMessage(message, smsg, InlineKeyboardMarkup(btns) if len(btns) != 0 else None)
        return
    try:
        arg = (await decode(txtargs[1])).split('-')
    except Exception as e:
        await rep.report(f"User : {uid} | Error : {str(e)}", "error")
        await editMessage(temp, "<b>Input Link Code Decode Failed !</b>")
        return
    if len(arg) == 2 and arg[0] == 'get':
        try:
            fid = int(int(arg[1]) / abs(int(Var.FILE_STORE)))
        except Exception as e:
            await rep.report(f"User : {uid} | Error : {str(e)}", "error")
            await editMessage(temp, "<b>Input Link Code is Invalid !</b>")
            return
        try:
            msg = await client.get_messages(Var.FILE_STORE, message_ids=fid)
            if msg.empty:
                return await editMessage(temp, "<b>File Not Found !</b>")
            nmsg = await msg.copy(message.chat.id, reply_markup=None)
            await temp.delete()
            if Var.AUTO_DEL:
                async def auto_del(msg, timer):
                    await asleep(timer)
                    await msg.delete()
                await sendMessage(message, f'<i>File will be Auto Deleted in {convertTime(Var.DEL_TIMER)}, Forward to Saved Messages Now..</i>')
                bot_loop.create_task(auto_del(nmsg, Var.DEL_TIMER))
        except Exception as e:
            await rep.report(f"User : {uid} | Error : {str(e)}", "error")
            await editMessage(temp, "<b>File Not Found !</b>")
    else:
        await editMessage(temp, "<b>Input Link is Invalid for Usage !</b>")

@bot.on_message(command('help') & private & user(Var.ADMINS))
@new_task
async def help_cmd(client, message):
    help_text = """<b>🤖 Admin Commands:</b>

<b>📋 General:</b>
• <code>/start</code> - Start the bot
• <code>/help</code> - Show this help message
• <code>/log</code> - Get bot log file

<b>🎛️ Control:</b>
• <code>/pause</code> - Pause anime fetching
• <code>/resume</code> - Resume anime fetching
• <code>/restart</code> - Restart the bot

<b>➕ Add Tasks:</b>
• <code>/addlink &lt;rss_url&gt;</code> - Add RSS feed link
• <code>/addtask &lt;rss_url&gt; [index]</code> - Add specific RSS task
• <code>/addmagnet &lt;magnet_link&gt;</code> - Add magnet link task

<b>🎉 Sticker Management:</b>
• <code>/togglesticker</code> - Enable/disable celebration stickers
• <code>/addsticker &lt;sticker_id&gt;</code> - Add new celebration sticker
• <code>/liststickers</code> - List all celebration stickers
• <code>/teststicker</code> - Test a random celebration sticker

<b>💡 Examples:</b>
<code>/addmagnet magnet:?xt=urn:btih:abc123...</code>
<code>/addsticker CAACAgUAAxkBAAEOyQtoXB1S...</code>
<code>/togglesticker</code>"""
    
    await sendMessage(message, help_text)
    
@bot.on_message(command('pause') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = False
    await sendMessage(message, "`Successfully Paused Fetching Animes...`")

@bot.on_message(command('resume') & private & user(Var.ADMINS))
async def pause_fetch(client, message):
    ani_cache['fetch_animes'] = True
    await sendMessage(message, "`Successfully Resumed Fetching Animes...`")

@bot.on_message(command('log') & private & user(Var.ADMINS))
@new_task
async def _log(client, message):
    await message.reply_document("log.txt", quote=True)

@bot.on_message(command('addlink') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Link Found to Add</b>")
    
    Var.RSS_ITEMS.append(args[0])
    req_msg = await sendMessage(message, f"`Global Link Added Successfully!`\n\n    • **All Link(s) :** {', '.join(Var.RSS_ITEMS)[:-2]}")

@bot.on_message(command('addtask') & private & user(Var.ADMINS))
@new_task
async def add_task(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Task Found to Add</b>")
    
    index = int(args[2]) if len(args) > 2 and args[2].isdigit() else 0
    if not (taskInfo := await getfeed(args[1], index)):
        return await sendMessage(message, "<b>No Task Found to Add for the Provided Link</b>")
    
    ani_task = bot_loop.create_task(get_animes(taskInfo.title, taskInfo.link, True))
    await sendMessage(message, f"<i><b>Task Added Successfully!</b></i>\n\n    • <b>Task Name :</b> {taskInfo.title}\n    • <b>Task Link :</b> {args[1]}")

@bot.on_message(command('addmagnet') & private & user(Var.ADMINS))
@new_task
async def add_magnet_task(client, message):
    if len(args := message.text.split(maxsplit=1)) <= 1:
        return await sendMessage(message, "<b>No Magnet Link Found to Add</b>\n\n<i>Usage:</i> <code>/addmagnet magnet:?xt=urn:btih:...</code>")
    
    magnet_link = args[1].strip()
    
    # Validate magnet link
    if not magnet_link.startswith("magnet:?xt=urn:btih:"):
        return await sendMessage(message, "<b>Invalid Magnet Link!</b>\n\n<i>Please provide a valid magnet link starting with 'magnet:?xt=urn:btih:'</i>")
    
    try:
        # Extract anime name from magnet link
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(magnet_link).query)
        anime_name = parsed.get('dn', ['Unknown Anime'])[0]
        anime_name = urllib.parse.unquote(anime_name)
        
        # Send confirmation message
        confirmation_msg = f"✅ <b>**Magnet Task Added!**</b>\n\n"
        confirmation_msg += f"🔸 <b>**Name:**</b> `{anime_name}`\n\n"
        confirmation_msg += f"🧲 <b>**Magnet:**</b> `{magnet_link[:50]}...`"
        
        await sendMessage(message, confirmation_msg)
        
        # Add the magnet task to processing queue
        ani_task = bot_loop.create_task(get_animes(anime_name, magnet_link, True))
        
        await rep.report(f"Manual Magnet Task Added: {anime_name}", "info")
        
    except Exception as e:
        await rep.report(f"Error adding magnet task: {str(e)}", "error")
        await sendMessage(message, f"<b>Error processing magnet link!</b>\n\n<i>Error: {str(e)}</i>")

@bot.on_message(command('togglesticker') & private & user(Var.ADMINS))
@new_task
async def toggle_sticker(client, message):
    Var.SEND_CELEBRATION_STICKER = not Var.SEND_CELEBRATION_STICKER
    status = "✅ Enabled" if Var.SEND_CELEBRATION_STICKER else "❌ Disabled"
    await sendMessage(message, f"<b>Celebration Stickers:</b> {status}")

@bot.on_message(command('addsticker') & private & user(Var.ADMINS))
@new_task
async def add_sticker(client, message):
    if len(args := message.text.split()) <= 1:
        return await sendMessage(message, "<b>No Sticker ID Found</b>\n\n<i>Usage:</i> <code>/addsticker &lt;sticker_file_id&gt;</code>")
    
    sticker_id = args[1].strip()
    
    try:
        # Test if sticker exists by trying to send it
        test_msg = await bot.send_sticker(chat_id=message.chat.id, sticker=sticker_id)
        await test_msg.delete()
        
        # Add to sticker list
        Var.CELEBRATION_STICKERS.append(sticker_id)
        await sendMessage(message, f"✅ <b>Sticker Added Successfully!</b>\n\n<b>Total Stickers:</b> {len(Var.CELEBRATION_STICKERS)}")
        
    except Exception as e:
        await sendMessage(message, f"❌ <b>Invalid Sticker ID!</b>\n\n<i>Error: {str(e)}</i>")

@bot.on_message(command('liststickers') & private & user(Var.ADMINS))
@new_task
async def list_stickers(client, message):
    if not Var.CELEBRATION_STICKERS:
        return await sendMessage(message, "<b>No celebration stickers configured.</b>")
    
    sticker_text = f"<b>🎉 Celebration Stickers ({len(Var.CELEBRATION_STICKERS)}):</b>\n\n"
    for i, sticker_id in enumerate(Var.CELEBRATION_STICKERS, 1):
        sticker_text += f"{i}. <code>{sticker_id}</code>\n"
    
    status = "✅ Enabled" if Var.SEND_CELEBRATION_STICKER else "❌ Disabled"
    sticker_text += f"\n<b>Status:</b> {status}"
    
    await sendMessage(message, sticker_text)

@bot.on_message(command('teststicker') & private & user(Var.ADMINS))
@new_task
async def test_sticker(client, message):
    from random import choice
    if not Var.CELEBRATION_STICKERS:
        return await sendMessage(message, "<b>No celebration stickers configured.</b>")
    
    try:
        sticker_id = choice(Var.CELEBRATION_STICKERS)
        await bot.send_sticker(chat_id=message.chat.id, sticker=sticker_id)
        await sendMessage(message, f"✅ <b>Test sticker sent successfully!</b>\n\n<code>{sticker_id}</code>")
    except Exception as e:
        await sendMessage(message, f"❌ <b>Failed to send test sticker!</b>\n\n<i>Error: {str(e)}</i>")
        # Remove invalid sticker
        if sticker_id in Var.CELEBRATION_STICKERS:
            Var.CELEBRATION_STICKERS.remove(sticker_id)
            await sendMessage(message, f"🗑️ <b>Removed invalid sticker from list</b>")
