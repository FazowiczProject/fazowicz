#!/usr/bin/env python3
import asyncio
import boto3
import datetime
import functools
import hashlib
from io import BytesIO
import hashlib
import json
import os
import random
from signal import signal
from time import sleep
import requests
import discord
import oauth
import re
import subprocess
from PIL import Image
from threading import Thread
import pika
import traceback
import uuid
import urllib.request

### gdrive stuff ###
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

intent_list = discord.Intents.all()
client = discord.Client(intents=intent_list)
BASE = "https://discord.com/api/v10/"
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/cloud-platform'
]

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# ! TODO: notifications part are using synchronous MQ !
# ! library, but entire stack is based on asyncio     !
# !                                                   !
# ! added at: 31.03.2023 23:29                        !
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
notifications_queue = None
mq_connection = None
mq_channel = None

config_save_regex = r"zapisz (?P<KEY>[a-z_]+) (?P<VALUE>.*)$"
init_dl_regex = r"init_dl (?P<URL>.*)$"
yt_stream_end_detection_regex = r"#EXT-X-PROGRAM-DATE-TIME:(?P<TIMESTAMP>.*)'"

BOT_TOKEN = ""
LOG_PATH = os.getenv("LOG_PATH") if os.getenv("LOG_PATH") != None else "fazowicz.log"
FAZOWICZ_CONFIG = os.getenv("FAZOWICZ_CONFIG") if os.getenv("FAZOWICZ_CONFIG") != None else "fazowicz_config.json"
TMP_PATH = "."
YOUTUBE_DL_TEMP = os.getenv("YOUTUBE_DL_TEMP") if os.getenv("YOUTUBE_DL_TEMP") != None else "/tmp"
VERSION = "1.5.6"

RELEASE_NOTES = {
    "1.3.1": "- fazowicz będzie co niedzielę o 19 będzie wysyłał to https://cdn.discordapp.com/attachments/931075845634793502/1012521948024143923/109.196.63.127-2022.03.03.1.11.11.jpg\n- można ręcznie wrzucić przez fazowicza ten obrazek na ogólny pisząc na administracyjnym kanale \"[małpa]fazowicz niedziela\"",
    "1.3.2": "- ochrona przed napływem - fazowicz będzie dawał kicka każdemu kto wejdzie na serwer jeśli w konfiguracji `naplyw_mode` jest ustawiony na `True` (domyślnie jest `False`)",
    "1.4.1": "- **głos AI** :sunglasses: (jeszcze w fazie testów ale jako tako działa)",
    "1.4.2": "- fazowicz będzie pisał \"chrumo\" na ogólnym jak odpali się syntezator mowy i \"nie ma chrumo...\" jak przestanie działać + jakieśtam bugfixy rużne",
    "1.4.4": "- dodanie powiadomień od Gordona na ogólnym",
    "1.5.1": "- pan fazowicz będzie dodawał rangę np. <@&922577407515430952> gdy włączona jest opcja `ranga_za_uszola` (lub losowo dawał bana)",
    "1.5.4": "- ajjj tydydy tyty da",
    "1.5.5": "- dodanie opcji `ja_uszol_zawsze_tak` (jeśli `True` - będzie banował nawet jeśli ktoś ma rangę np. <@&922577407515430952>, jeśli nie to będzie ignorował tych użytkowników)",
    "1.5.6": "- stare zachowanie weryfikacyjne (przed wersją 1.5.1 czyli zamiast dodawać rangę policja to powinien weryfikować że hoho)"
}

if not YOUTUBE_DL_TEMP.endswith('/'):
    YOUTUBE_DL_TEMP = YOUTUBE_DL_TEMP + '/'


yt_dl_process = None
current_processing_url = None

aiservice_running = False

default_config = {
    'wlaczony': True,
    'przerwy_za_uszola': True,
    'odpisywanie_na_tagowanie': True,
    'odpisywanie_na_slowa_kluczowe': True,
    'odpisywanie_na_wylaczonego_uszola': True,
    'shitposting': True,
    'nitraxgate': False,
    'nitraxes': '', # list of user IDs (i.e: '1035086035387953173,708822208776241202')
    'nitrax_channel_id': '945724435216891955',
    'internal_admin_role_id': '931075845634793502',
    'internal_cnc_channel_id': '950798777688670298',
    'verification_period_min': 60,
    'verification_period_max': 604760,
    'verification_count': 1720,
    'upstream_channel_id': '854041386163634178',
    'live_stream_shot_backoff_time': 60,
    'randsynth': True,
    'randsynth_pitch': 1.1428571428571428571428571428571,
    'randsynth_chance': 1,
    'randsynth_min_words': 300,
    'version': '1.5.6',
    'powitalny_id': '854046608907567165',
    'naplyw_mode': False,
    'aiservice_enabled': False,
    'aiservice_healthcheck_url': 'https://example.com/api/v1/health',
    'aiservice_url': 'https://example.com/api/v1/synth',
    'aiservice_gan': True,
    'aiservice_voice': 'szwed_600epochs.tt2',
    'reupload_notifications': True,
    'ranga_za_uszola': False,
    'ranga_za_uszola_id': '922577407515430952',
    'ranga_za_uszola_chance': 0.5,
    'ja_uszol_zawsze_tak': False,
    'powitalny_id': '854046608907567165'
}
config = {}

def load_config():
    global config
    if not os.path.exists(FAZOWICZ_CONFIG):
        log("Creating config file")
        with open(FAZOWICZ_CONFIG, 'wt') as f:
            json.dump(default_config, f)

    with open(FAZOWICZ_CONFIG, 'rt') as f:
        config = json.load(f)
        return config

def get_config_value(key):
    global config
    return config[key]

def save_config_value(key, value):
    global config
    if value == "True":
        value = True
    if value == "False":
        value = False

    config[key] = value

    with open(FAZOWICZ_CONFIG, 'wt') as f:
        json.dump(config, f)
    load_config()


def log(*printargs):
    logline = '[' + str(datetime.datetime.now()) + '] ' + ' '.join(list(map(lambda arg: str(arg), printargs)))
    print(logline)
    with open(LOG_PATH, 'a') as f:
        f.write(logline + '\n')

def timeout_user(*, user_id: int, guild_id: int, bot_token: str):
    endpoint = f'guilds/{guild_id}/members/{user_id}'
    headers = {
        "Authorization": f"Bot {bot_token}"
    }
    url = BASE + endpoint
    random_timeout = int((random.random() * float(get_config_value('verification_period_max'))) + int(get_config_value('verification_period_min')))
    timeout = (datetime.datetime.utcnow() + datetime.timedelta(seconds=random_timeout)).isoformat()
    json = {'communication_disabled_until': timeout}
    session = requests.patch(url, json=json, headers=headers)
    if session.status_code in range(200, 299):
        return session.json()
    else:
        log(f"Failed to timeout user {user_id} - Discord API returned HTTP {session.status_code}")
        print(session.content.decode('utf-8'))
        return print("Did not find any\n", session.status_code)

def ai_synth(prompt, gan, target_file):
    try:
        access_token = oauth.get_access_token()
        log('!!! CALLING AI SERVICE !!!')
        endpoint = get_config_value('aiservice_url')
        response = requests.post(endpoint, json={
            'prompt': prompt,
            'gan': gan
        }, stream=True, headers={
            'Authorization': 'Bearer ' + access_token
        })

        if response.status_code == 200:
            with open(target_file, 'wb') as f:
                for chunk in response.iter_content(chunk_size=4096):
                    f.write(chunk)
            return True
        else:
            return False
    except:
        return False

@client.event
async def on_command_error(ctx, error):
    log(error)

prefixes = [
    'zamknij morde',
    'morda'
]

messages = [
    'wiesz tam na te strony to moze twoja matka isc',
    'nie podoba sie to wypierdalaj',
    'swiniom nie rzuca sie perel',
    'nie bedzie labamby na kranie'
]

lucas_messages = [
    'oj tak!',
    'tak jest!'
]

drunk_messages = [
    'nie zamulamy robimy mocne challenge dymy',
    'wysylamy donejty',
    'wiesz bartek pisze cv',
    'ten challenge jest zabroniony',
    'niech rządzi pis pis pis pis jest święty pis jest najlepszy',
    ':earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa: :earth_africa:'
]

meme_triggers = ['Uszaty', 'labamba', 'Daniel Lolek', 'glasgow', 'Piękny Tomuś', 'Marcin Gwóźdź', 'Nożyczki', 'Lepa od Tomusia', 'Wanna', 'Luiza z PalhajsTV', 'Lukas', 'Babka Himmel', 'Rozmowa z Girl', 'Gamingowy Dzban', 'NYO Travel', 'Sranie na live', 'Spoko spoko Bejblade', 'Mirosław Sz.', 'Mocny donejt', 'Pompka do fiuta', 'Staś Pomidor', 'Szwed wali', 'MrElWood', 'Zamknij morde Bilgunka', 'Vivus', 'Michaszki', 'Ruchanie Wersow', 'Bluza Galaxy', 'Justin Bieber', 'Selena Gomez', 'Wuwunio', 'Tiger Bonzo', 'Kobra', 'Seba je kupe', 'Gamingowy dzban', 'Barmańska', 'Przyjaciel z kosmosu', 'Asortyment', 'Skierniewice', 'Klimat rancza', 'skierniewickie Chicago', 'amerykański klimat', 'amerykańska mentalność', 'Team four us', 'pompka do chuja', 'skierniewicka afryka', 'gąbka babci', 'żołnierz z ziemi', 'oszi', 'link w opisie', 'cennik', 'jedzenie kupy', 'ale faza', 'spuchnięta morda', 'uszaty bez kasy', 'ogórkowa', 'faza katola', 'badboy ruchacz', 'dominic toretto', 'stanie na kranie', 'labamba na kranie', 'fotograf', 'Paweł', 'czapka na grzyby', 'małpka', 'FAS', 'AU', 'Milioner z ulicy', 'Glucia', 'czapka z biedronki', 'mr hajs', 'Radio zachariasz', 'Daniel Bolek', 'iceberg', 'bezdomny', 'ps4', 'jakość 4k', 'ranczo', 'mama piła w ciąży', 'żul party', 'chłopiec z tiktoka', 'perkusista', 'wysmarowany masłem', 'babka himmel', 'czapka ekipy', 'giorgio armani', 'sztuczna cipa', 'mc himmel', 'dźwi', 'martini', 'bandana', 'zakola', 'próchnica', 'jedynki', 'upside down', 'vin diesel', 'szybcy i wściekli', 'Buenos Aires', 'chore serce', 'król łez', 'krór łez']

def generate_meme():
    image_data = json.load(open("image_data.json"))
    template = random.choice(image_data["templates"])
    template_image = Image.open(template["template_path"])

    unique_substitutes = []
    for _ in template["possible_substitutes"]:
        selected_image = random.choice(image_data["substitutes"])
        while selected_image in unique_substitutes:
            selected_image = random.choice(image_data["substitutes"])

        unique_substitutes.append(selected_image)            

    meme = Image.new("RGBA", (template_image.size[0], template_image.size[1]))
    meme.paste(template_image)
    del template_image

    counter = 0
    for image_to_substitute in template["possible_substitutes"]:
        image_to_paste = Image.open(unique_substitutes[counter]).convert("RGBA").resize((image_to_substitute["dst_w"], image_to_substitute["dst_h"]))
        meme.paste(image_to_paste, (image_to_substitute["dst_x"], image_to_substitute["dst_y"]))    
        del image_to_paste # let's save some memory
        counter = counter + 1

    meme_buffer = BytesIO()
    meme.save(meme_buffer, format="png")
    meme_buffer.seek(0) # rewind memory buffer for discord.py
    del meme # already rendered in buffer
    return meme_buffer

class YoutubeDlAsyncIterator:
    def __init__(self, yt_dl_process):
        self.yt_dl_process = yt_dl_process

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            print(yt_dl_process)
            return await asyncio.get_event_loop().run_in_executor(None, yt_dl_process.stdout.readline)
        except:
            raise StopAsyncIteration

def upload_shot(shot_path, filename):
    creds = service_account.Credentials.from_service_account_file('google_credentials.json', scopes=SCOPES)

    try:
        service = build('drive', 'v3', credentials=creds)
        file_metadata = {'name': filename}
        media = MediaFileUpload(shot_path,
                                mimetype='video/mp4', resumable=True)
        # pylint: disable=maybe-no-member
        file = service.files().create(body=file_metadata, media_body=media,
                                      fields='id').execute()
        log(F'File ID: {file.get("id")}')
        file_id = file.get("id")
        user_permission = {
            'type': 'anyone',
            'role': 'reader',
        }
        service.permissions().create(fileId=file_id,
                                    body=user_permission,
                                    fields='id'
        ).execute()
        return file_id
    except HttpError as error:
        log(f'An error occurred: {error}')              

# TODO: move me to yt-dlp so all this untrunc crap can be removed
async def download_video(url):
    global yt_dl_process
    global current_processing_url
    last_timestamp = None
    current_timestamp = None
    same_timestamp_count = 0

    info_channel = await client.fetch_channel(get_config_value('internal_cnc_channel_id'))
    if yt_dl_process != None:
        log("ERROR: youtube-dl process already running !!!")
        info_channel.send("ERROR: youtube-dl process already running !!! " + str(yt_dl_process) + " " + url)
        return
    
    # youtube-dl -o "/tmp/%(title)s-%(id)s.%(ext)s"
    temp_filename = hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".mp4"
    log("Initiating download of video/stream", url)
    yt_dl_process = subprocess.Popen(["youtube-dl", "-o", YOUTUBE_DL_TEMP + temp_filename, url],
        shell=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    current_processing_url = url

    await info_channel.send("Rozpoczęto pobieranie filmu " + url)
    async for line in YoutubeDlAsyncIterator(yt_dl_process=yt_dl_process):
        try:
            decoded_line = line.decode('utf-8')
            log(line)
            match = re.search(yt_stream_end_detection_regex, decoded_line)
            if match != None:
                last_chunk_timestamp = match.group('TIMESTAMP')
                log('Last timestamp:', last_chunk_timestamp)
                current_timestamp = last_chunk_timestamp
                if current_timestamp != None and last_timestamp != None and (current_timestamp.strip() == last_timestamp.strip()):
                    same_timestamp_count = same_timestamp_count + 1
                    log('Same timestamp occurred', same_timestamp_count, 'times ...')
                else:
                    if same_timestamp_count > 0:
                        log('Same timestamp has changed - resetting counter...')
                    same_timestamp_count = 0

                last_timestamp = last_chunk_timestamp

                if same_timestamp_count >= int(get_config_value('live_stream_shot_backoff_time')):
                    yt_dl_process.send_signal(2)
                    yt_dl_process = None
                    log('yt-dl finished.')
                    break
        except UnicodeDecodeError:
            log('Ignoring line', line, 'due to UnicodeDecodeError')  

    log('Video download finished gracefully.')
    current_processing_url = None
    path_to_process = YOUTUBE_DL_TEMP + temp_filename

    log('Waiting for ffmpeg to stop producing file...')
    await asyncio.sleep(5)
    if os.path.exists(YOUTUBE_DL_TEMP + temp_filename + '.part'):
        path_to_process = YOUTUBE_DL_TEMP + temp_filename + '.part'

    untrunc_cmd = 'untrunc -dst ' + YOUTUBE_DL_TEMP + temp_filename + '.fixed.mp4 reference.mp4 ' + path_to_process
    print(untrunc_cmd)
    untrunc_process = await asyncio.create_subprocess_shell(untrunc_cmd)
    await untrunc_process.communicate()
    log('Untrunc exit code:', untrunc_process.returncode)
    if untrunc_process.returncode == 0:
        os.unlink(path_to_process)
        log('Deleted temp file -', path_to_process)
        file_id = upload_shot(YOUTUBE_DL_TEMP + temp_filename + '.fixed.mp4', temp_filename + '.mp4')
        await info_channel.send("Reup - " + "https://drive.google.com/file/d/" + file_id)
    

async def post_meme():
    upstream_channel = await client.fetch_channel(get_config_value('upstream_channel_id'))
    meme = generate_meme()
    await upstream_channel.send(file=discord.File(meme, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".png"))
    del meme

async def niedziela():
    with open('niedziela.jpg', 'rb') as f:
        upstream_channel = await client.fetch_channel(get_config_value('upstream_channel_id'))
        await upstream_channel.send(file=discord.File(f, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".png"))    

async def posting_thread():
    global aiservice_running
    while True:
        current_timestamp = datetime.datetime.now()
        if (current_timestamp.hour == 12 and current_timestamp.minute == 15) and get_config_value('shitposting') == True:
            await post_meme()

        if (current_timestamp.weekday() == 6 and current_timestamp.hour == 19 and current_timestamp.minute == 0) and get_config_value('shitposting') == True:
            await niedziela()

        await asyncio.sleep(60)

def shellquote(s):
    return "'" + s.replace("'", "'\\''") + "'"

def aiservice_healthcheck():
    try:
        response = requests.get(get_config_value('aiservice_healthcheck_url'))
        return response.status_code == 200
    except:
        return False

async def synth(message):
    filename = hashlib.md5(str(random.random()).encode('ascii')).hexdigest()

    if get_config_value('aiservice_enabled') == True:
        result = ai_synth(message.content.strip(), get_config_value('aiservice_gan'), '/tmp/' + filename)
    else:
        result = False
    
    if not result: # fallback if AI service is dead
        synth_cmd = 'espeak -v pl -s 100 -p 70 -w /tmp/' + filename + ' ' + shellquote(message.content.strip())
        print(synth_cmd)
        untrunc_process = await asyncio.create_subprocess_shell(synth_cmd)
        await untrunc_process.communicate()    

    imagefile = 'maxszwef.png' if result == True else 'randsynth_noalpha.png'
    audio_noai = '-af asetrate=44100*' + str(get_config_value('randsynth_pitch')) + ',aresample=44100,atempo=1/' + str(get_config_value('randsynth_pitch'))
    audio_ai = '-ar 44100'
    audio_cmd = audio_ai if result == True else audio_noai

    synth_cmd = 'ffmpeg -loop 1 -i ' + imagefile + ' -i /tmp/' + filename + ' -s 720x1080 -vf format=yuv420p ' + audio_cmd + ' -shortest /tmp/' + filename + '.mp4'
    print(synth_cmd)
    untrunc_process = await asyncio.create_subprocess_shell(synth_cmd)
    await untrunc_process.communicate()
    with open('/tmp/' + filename + '.mp4', 'rb') as f:
        await message.reply(file=discord.File(f, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".mp4"))
        os.remove('/tmp/' + filename)
    os.remove('/tmp/' + filename + '.mp4')        

def upload_to_s3(source, target): # TODO: i don't think that it's used anymore
    s3_client = boto3.client(
        service_name='s3', 
        endpoint_url="...", 
        aws_access_key_id="...",
        aws_secret_access_key="...",
        region_name="us-east-1"
    )

    s3_client.upload_file(source, "ai-results", target)    
    response = s3_client.generate_presigned_url('get_object',
                                                Params={'Bucket': 'ai-results',
                                                        'Key': target},    
    )
    log("S3 done")
    return response

@client.event
async def on_message(message):
    try:
        global BOT_TOKEN
        log(message)
        log('[#' + message.channel.name + '] ' + message.author.name + ': ' + message.content)
        if str(message.channel.id) == get_config_value('internal_cnc_channel_id') and client.user.mentioned_in(message):
            log(f'>>> ADMIN COMMAND FROM {message.author}')
            if 'konfiguracja' in message.content.lower() and message.author != client.user:
                message_to_send = "OBECNA KONFIGURACJA BOTA\n========================\n\n"
                for key, value in config.items():
                    message_to_send = message_to_send + f'{key} => {value}\n'

                await message.channel.send(message_to_send.strip())
            elif 'zapisz' in message.content.lower() and message.author != client.user:
                save_config_match = re.search(config_save_regex, message.content)
                if save_config_match == None:
                    log('>>> ADMIN INVALID SAVE SYNTAX')
                    return
                
                config_key_to_save = save_config_match.group('KEY')
                config_value_to_save = save_config_match.group('VALUE')
                save_config_value(config_key_to_save, config_value_to_save)
                await message.channel.send(f'Zapisano wartość {config_value_to_save} dla ustawienia {config_key_to_save}')
            elif 'shitpost' in message.content.lower() and message.author != client.user:
                await post_meme()
            elif 'init_dl' in message.content.lower() and message.author != client.user:
                init_dl_match = re.search(init_dl_regex, message.content)
                if init_dl_match == None:
                    log('>>> ADMIN INVALID DL SYNTAX')
                    await message.channel.send("Invalid init_dl syntax - URL not found in command")
                    return
                
                url = init_dl_match.group('URL').strip()
                client.loop.create_task(download_video(url))
            elif 'rn' in message.content.lower() and message.author != client.user:
                await release_notes(message.channel.id, True)
            elif 'niedziela' in message.content.lower() and message.author != client.user:
                await niedziela()          
            return

        if get_config_value('wlaczony') == True:
            if client.user.mentioned_in(message) and (not message.mention_everyone) and (message.author != client.user) and get_config_value('odpisywanie_na_tagowanie') == True:
                await message.channel.send(f'{random.choice(prefixes)} <@{message.author.id}> {random.choice(messages)}')

            if get_config_value('randsynth') == True and message.author != client.user and random.random() < float(get_config_value('randsynth_chance')) and len(message.content) >= int(get_config_value('randsynth_min_chars')):
                await synth(message)

            if ('uszol' in message.content.lower()) and message.author != client.user and get_config_value('przerwy_za_uszola') == True:
                timeout_user(user_id=message.author.id, guild_id=message.guild.id, bot_token=BOT_TOKEN)                    
                verification_count = int(get_config_value('verification_count'))
                verification_count = verification_count + 1
                save_config_value('verification_count', verification_count)
                await message.channel.send(f'<@{message.author.id}> weryfikacja pomyślna! :white_check_mark: Gratulacje! Zweryfikowanych użytkowników: **' + str(verification_count) + '**')
            elif ('uszol' in message.content.lower()) and message.author != client.user and get_config_value('przerwy_za_uszola') == False and get_config_value('odpisywanie_na_wylaczonego_uszola') == True:
                await message.channel.send(f'<@{message.author.id}> weryfikacja nie przebiegła pomyślnie - system wykrył ze jesteś botem. :no_entry: Żegnaj...')
            elif ('ogr' in message.content.lower() or
                'ork' in message.content.lower()) and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                if random.random() < 0.6:
                    await message.channel.send(f'{random.choice(prefixes)} <@{message.author.id}> ogrem jestes ty i twoj stary')
            elif ('mirek' in message.content.lower() or
                'miro' in message.content.lower()) and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.channel.send(f'<@{message.author.id}> mojego ojca to mam w dupie')
            elif ('lukas' in message.content.lower() or
                'luki' in message.content.lower() or
                'lucas' in message.content.lower()) and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.channel.send(f'<@{message.author.id}> {random.choice(lucas_messages)}')
            elif ('drunk' or 'stream') in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.channel.send(f'<@{message.author.id}> {random.choice(drunk_messages)}')
            elif 'showup' in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.channel.send(f'<@{message.author.id}> showup za kwote {int((random.random() * 900) + 100)}zl')
            elif '1215' in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.add_reaction('1️⃣')
                await message.add_reaction('2️⃣')
                await message.add_reaction('ℹ')
                await message.add_reaction('5️⃣')
            elif 'bóg wybacza' in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.channel.send(f'<@{message.author.id}> ale nie tobie kurwo jebana szmato')
            elif message.content.lower().strip() == '<:ta:1019586333758468187>' and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.reply('ta? to zajebiście')
            elif 'mocz' in message.content.lower().strip() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await message.reply('my mamy w sobie mocz')
            elif 'pytanie' in message.content.lower().strip() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                with open('substitutes/pytanie.png', 'rb') as f:
                    await message.reply(file=discord.File(f, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".png"))            
            elif '68a67bd780c2560818070e227e606f453d66f3c9464667ad9c7f40cf9304950a' in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                meme = generate_meme(file=discord.File(meme, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".png"))
                await message.channel.send(file=discord.File(meme, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".png"))
                del meme
            elif '68a67bd780c2560818070e227e606f453d66f3c9464667ad9c7f40cf9304950b' in message.content.lower() and message.author != client.user and get_config_value('odpisywanie_na_slowa_kluczowe') == True:
                await synth('lorem ipsum doloret sit amet')           
            elif random.random() < 0.7 and message.content.lower() in list(map(lambda trigger: trigger.lower(), meme_triggers)) and message.author != client.user and get_config_value('shitposting') == True:
                await post_meme()
            elif str(message.author.id) in get_config_value('nitraxes').split(',') and message.author != client.user and get_config_value('nitraxgate') == True:
                if str(message.channel.id) != get_config_value('nitrax_channel_id'):
                    timeout_user(user_id=message.author.id, guild_id=message.guild.id, bot_token=BOT_TOKEN)
                    verification_count = int(get_config_value('verification_count'))
                    verification_count = verification_count + 1
                    save_config_value('verification_count', verification_count)
                    await message.channel.send(f'<@{message.author.id}> weryfikacja pomyślna! :white_check_mark: Gratulacje! W ramach konkursu przydzielono Ci specjalną rangę <@&931166432027344917>! Zweryfikowanych użytkowników: **' + str(verification_count) + '**')
            elif get_config_value('naplyw_mode') == True and message.author != client.user:
                if str(message.channel.id) == get_config_value('powitalny_id') and message.type == discord.MessageType.new_member:
                    log("Args matched - kicking user")
                    await message.author.kick()

            if len(message.attachments) > 0 and message.author != client.user:
                for attachment in message.attachments:
                    if "audio/" in attachment.content_type:
                        job_id = str(uuid.uuid4())
                        os.system('curl --output /tmp/' + job_id + ' -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0" ' + attachment.url)
                        os.system('ffmpeg -i /tmp/' + job_id + ' /tmp/' + job_id + '.wav')
                        os.system('rm -rvf /tmp/' + job_id)
                        cloud_url = upload_to_s3('/tmp/' + job_id + '.wav', 'input_'+ job_id +'.wav')
                        os.system('rm -rvf /tmp/' + job_id + '.wav')
                        vc_request = {
                            'input': cloud_url,
                            'metadata': {
                                'faz:messageId': str(message.id),
                                'faz:channelId': str(message.channel.id)
                            }
                        }
                        publish_callback = functools.partial(send_to_vc_processing, mq_channel, vc_request)
                        mq_connection.add_callback_threadsafe(publish_callback)
    except Exception as e:
        log("Error!")
        log(str(e) + "\n" + traceback.format_exc())

def send_to_vc_processing(channel, request):
    channel.basic_publish(exchange='voc_transform', routing_key='demucs', body=json.dumps(request).encode("utf-8"))

async def release_notes(channel_id=None, bypass_version_check=False):
    global VERSION, RELEASE_NOTES
    if get_config_value('version') != VERSION or bypass_version_check:
        cnc_channel = await client.fetch_channel(get_config_value('internal_cnc_channel_id') if channel_id == None else channel_id)
        save_config_value('version', VERSION)
        message = 'NOWY FAZOWICZ DROPNĄŁ AUUU - wersja **' + VERSION + '**\n'
        should_send_message = False
        for release_note_ver, release_note_content in RELEASE_NOTES.items():
            if VERSION == release_note_ver:
                message = message + release_note_content + '\n'
                should_send_message = True

        if should_send_message:
            log(message)
            await cnc_channel.send(message)
            general = await client.fetch_channel(get_config_value('upstream_channel_id'))
            with open('erekcja.mp4', 'rb') as f:
                await general.send(file=discord.File(f, "erekcja.mp4"))

async def mq_asyncio_queue_consumer():
    exception_handled_already = False
    global notifications_queue

    log('[MQ async glue] Starting AMQP <-> asyncio glue')
    while True:
        try:
            next_message = await notifications_queue.get()
            upstream_channel = await client.fetch_channel(get_config_value(next_message['target']))
            replying = next_message['respond_to_message'] != None
            file_to_send = None
            if next_message['is_file']:
                with open(next_message['content'], 'rb') as f:
                    file_to_send = discord.File(f, filename=hashlib.md5(str(random.random()).encode('ascii')).hexdigest() + ".mp3")
            
            if replying:
                reply_channel = await client.fetch_channel(next_message['respond_to_message_channel_id'])
                message_to_reply = await reply_channel.fetch_message(int(next_message['respond_to_message']))
                await message_to_reply.reply(file=file_to_send)
            else:
                await upstream_channel.send(next_message['content'])
        except Exception as e:
            if not exception_handled_already:
                admin_channel = await client.fetch_channel(get_config_value('internal_cnc_channel_id'))
                await admin_channel.send('mq_asyncio_queue_consumer: ' + str(e) + '\n' + traceback.format_exc() + '\n\n<@012345678901234567> zjebalo sie cos')
                exception_handled_already = True

async def setup_threads():
    global notifications_queue
    await release_notes()
    asyncio.get_event_loop().create_task(posting_thread())

    notifications_queue = asyncio.Queue()
    mq_thread = Thread(target=mq_thread_handler)
    mq_thread.start()
    asyncio.get_event_loop().create_task(mq_asyncio_queue_consumer())

def mq_handler(channel, method, properties, body):
    log('[MQ] Handling notification')
    global notifications_queue

    respond_to_message = None
    respond_to_message_channel_id = None
    is_file = False
    content = None
    print(method)
    if method.exchange == 'ai_results':
        job_id = str(uuid.uuid4())
        decoded_body = json.loads(body)
        urllib.request.urlretrieve(decoded_body['result'], '/tmp/' + job_id + '.mp3')
        is_file = True
        respond_to_message = decoded_body['metadata']['faz:messageId']
        respond_to_message_channel_id = decoded_body['metadata']['faz:channelId']
        content = '/tmp/' + job_id + '.mp3'
    else:
        decoded_body = json.loads(body)
        is_reupload = decoded_body['is_reupload']
        reupload_url = decoded_body['reupload_url']
        content = reupload_url if is_reupload == False else 'REUP - ' + reupload_url

    try:
        notifications_queue.put_nowait({
            'target': 'upstream_channel_id',
            'content': content,
            'respond_to_message': respond_to_message,
            'respond_to_message_channel_id': respond_to_message_channel_id,
            'is_file': is_file
        })
    except:
        notifications_queue.put_nowait({
            'target': 'internal_cnc_channel_id',
            'content': 'mq_thread_handler: ' + str(e) + '\n' + traceback.format_exc() + '\n\n<@012345678901234567> zjebalo sie cos',
            'respond_to_message': None,
            'is_file': False
        })

def mq_thread_handler():
    global mq_connection
    global mq_channel
    exception_handled_already = False
    global notifications_queue
        
    try:
        log("[MQ] Starting thread")
        with open("amqp.json", "r") as f:
            amqp_config = json.load(f)
        
        log("[MQ] Loaded AMQP config")
        mq_connection = pika.BlockingConnection(pika.ConnectionParameters(host=amqp_config['host'], credentials=pika.PlainCredentials(username=amqp_config['user'], password=amqp_config['pass'])))
        mq_channel = mq_connection.channel()
        mq_channel.basic_consume(
            queue='notifications', on_message_callback=mq_handler, auto_ack=True)
        
        mq_channel.basic_consume(
            queue='ai_results', on_message_callback=mq_handler, auto_ack=True)        

        log('[MQ] Notifications consumer started')
        mq_channel.start_consuming()        
    except Exception as e:
        if not exception_handled_already:
            notifications_queue.put_nowait({
                'target': 'internal_cnc_channel_id',
                'content': 'mq_thread_handler: ' + str(e) + '\n' + traceback.format_exc() + '\n\n<@012345678901234567> zjebalo sie cos',
                'respond_to_message': None,
                'is_file': False                
            })
            exception_handled_already = True

async def main():
    global BOT_TOKEN
    log("Loading bot token...")
    with open('token', 'rb') as f:
        BOT_TOKEN = f.readline().decode('utf-8').strip()
    
    log("Bot ready for connection")
    log("Loading config file")
    load_config()

    log("Starting")
    
    client.setup_hook = lambda: setup_threads()
    await client.start(BOT_TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
