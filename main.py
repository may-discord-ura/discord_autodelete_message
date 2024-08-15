import os
import discord
import json
import datetime
import asyncio

from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta

# インテントの生成
intents = discord.Intents.default()
intents.message_content = True

# botの定義
bot = commands.Bot(intents=intents, command_prefix="$", max_messages=10000)
tree = bot.tree

# 設定ファイルのパス
CONFIG_FILE = 'config.json'
AUTODELETE_LIST = 'autodelete.json'

### --------関数定義ゾーン---------
# 設定を読み込む
def load_config(file):
    with open(file, 'r') as f:
        return json.load(f)


# 設定を書き込む
def save_config(config, file):
    with open(file, 'w') as f:
        json.dump(config, f, indent=4,ensure_ascii=False)

# autodeleteで削除したメッセージをテキストに書き出す
def log_deleted_messages(channel_name, messages):
    date_str = datetime.datetime.now(server_timezone).strftime("%Y-%m-%d")
    log_file = f"autodelete_log/{channel_name}[{date_str}].txt"

    # 既存のログファイルを読み込む
    existing_logs = []
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            existing_logs = f.readlines()

    # 新しいログエントリを追加
    new_logs = []
    for message in messages:
        # 通常メッセージまたはembedのdescriptionをログに保存
        content = message.content.replace('\n', ' \\n ')
        if message.embeds:
            for embed in message.embeds:
                if embed.description:
                    content = embed.description.replace('\n', ' \\n ')
        content = content.replace(',', '，`')
        if content == "":
            content = "本文なし"
        posted_time = message.created_at.astimezone(server_timezone).strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{posted_time},{message.author.id},{message.author.name},{content}\n"
        new_logs.append(log_entry)

    # 既存のログと新しいログを統合してソート
    all_logs = existing_logs + new_logs
    all_logs.sort()  # timestampが最初に来るので、文字列としてソートすれば時系列順になる

    # ログファイルに書き込む
    with open(log_file, "w", encoding="utf-8") as f:
        f.writelines(all_logs)


### -----on_readyゾーン------
# discordと接続した時に呼ばれる
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}.")
    await tree.sync()
    print("Synced slash commands.")


    """設定をファイルから読み込む"""
    global config
    global server_timezone
    global autodelete_config

    if os.path.exists(CONFIG_FILE):
        # 初期設定の読み込み
        config = load_config(CONFIG_FILE)
    else:
        config = {}    
    if config.get('server_timezone', "UTC") == "JST":# タイムゾーンを定義
        JST = datetime.timezone(timedelta(hours=+9), 'JST')
        server_timezone = JST
    else:
        UTC = datetime.timezone(timedelta(hours=+0), 'UTC')
        server_timezone = UTC


    if os.path.exists(AUTODELETE_LIST):
        autodelete_config = load_config(AUTODELETE_LIST)
    else:
        autodelete_config = {}
        save_config(autodelete_config, AUTODELETE_LIST)

    # ループ起動
    delete_old_messages.start()

###スラッシュコマンド
# メッセージ自動削除対象の登録
# チャンネル内のメッセージが多すぎると不具合が起きる可能性あり
@tree.command(name="レス自動削除設定", description="このチャンネルのレス自動削除設定をします")
@app_commands.describe(
    minutes="メッセージを削除するまでの時間（分単位）※0を指定すると自動削除しなくなり、省略すると現在の設定を表示します",
    ログ保存="削除したメッセージをテキストファイルに書き出すかどうかを設定します（デフォルト：False）"
)
async def auto_delete(interaction: discord.Interaction, minutes: int = -1, ログ保存:bool=False):
    target_id = str(interaction.channel_id)  # コマンドが実行されたチャンネルまたはスレッドのID
    global autodelete_config
    # 設定の表示、更新または削除
    if minutes == -1:
        if target_id in autodelete_config:
            current_minutes = autodelete_config[target_id]
            await interaction.response.send_message(
                f"このチャンネル（スレッド）では {current_minutes} 分後にメッセージが自動削除されます。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "このチャンネル（スレッド）では自動削除を行わない設定になっています。",
                ephemeral=True
            )
        return
    elif minutes == 0:
        if target_id in autodelete_config:
            del autodelete_config[target_id]
            save_config(autodelete_config,AUTODELETE_LIST)
            await interaction.response.send_message(
                f"{interaction.channel.mention} の設定が削除されました。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{interaction.channel.mention} には設定がありません。",
                ephemeral=True
            )
    elif minutes < 5 or minutes > 10080:
        await interaction.response.send_message("時間を5分～10080分の間で指定してください",ephemeral=True)
        return
    else:
        autodelete_config[target_id] = {'minutes': minutes,'ログ保存': ログ保存}
        save_config(autodelete_config,AUTODELETE_LIST)
        if ログ保存 is True:
            await interaction.response.send_message(
                f"{interaction.channel.mention} でメッセージを {minutes} 分後に削除するように設定しました。\nログはautodeleteフォルダに保存されます。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"{interaction.channel.mention} でメッセージを {minutes} 分後に削除するように設定しました。\nログは保存しません。",
                ephemeral=True
            )
        

    

    await delete_old_messages()

### --------------loopコーナー-------------- ###
# 指定チャンネル・スレッドでのメッセージ自動削除
@tasks.loop(minutes=15)
async def delete_old_messages():
    if autodelete_config == {}:
        return

    now = datetime.datetime.today().astimezone(server_timezone)
    fourteen_days_ago = now - timedelta(days=14)
    to_delete_id=[]
    for target_id, settings in autodelete_config.items():
        try:
            target = bot.get_channel(int(target_id)) or bot.get_thread(int(target_id))
        except Exception: # 指定したチャンネルが見つからなかった場合、設定を削除する
            to_delete_id.append(target_id)
            continue
        if target:
            minutes = settings['minutes']
            to_delete = []
            threshold = now - timedelta(minutes=minutes)
            async for message in target.history(before=threshold, limit=None):
                message_creation_time = message.created_at
                if message.id == int(target_id) or message.pinned or message_creation_time < fourteen_days_ago:
                    continue  # スターターメッセージとピン止めと14日以上前のメッセージは削除しない
                if now - message_creation_time > timedelta(minutes=minutes):
                    to_delete.append(message)
                if len(to_delete) >= 100:
                    await target.delete_messages(to_delete)
                    if settings['ログ保存'] is True:
                        log_deleted_messages(target.name, to_delete)#削除した分だけログファイルに書き込み
                    to_delete = []
                    await asyncio.sleep(1)  # レートリミットを避けるための待機

            # 残りのメッセージを削除
            if to_delete:
                await target.delete_messages(to_delete)
                if settings['ログ保存'] is True:
                    log_deleted_messages(target.name, to_delete)#削除した分だけログファイルに書き込み
                to_delete = []

    # 見つからなかったチャンネルIDをリストから削除
    for target_id in to_delete_id:
        del autodelete_config[target_id]
    save_config(autodelete_config,AUTODELETE_LIST)


@delete_old_messages.before_loop
async def before_delete_old_messages():
    await bot.wait_until_ready()

# クライアントの実行
bot.run(os.environ["TOKEN"])
