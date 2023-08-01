import hashlib as hl
import json
import os
from configparser import ConfigParser
from urllib.parse import quote

import bcrypt
import mysql.connector
import requests

print("Starting...")

config = ConfigParser()
config.read("updater_config.ini")

print("Enter your user ID: ")
user_id = input()
my_db = mysql.connector.connect(
    host=config["Database"]["Host"],
    user=config["Database"]["Username"],
    password=config["Database"]["Password"],
    database=config["Database"]["Database"],
    port=config["Database"]["Port"]
)
cursor = my_db.cursor()
cursor.execute("SELECT * FROM Passwords WHERE userID = %s", (user_id,))
result = cursor.fetchone()
if result is None:
    print("Error: User ID not found")
    exit(1)

print("Enter your password: ")
user_password = input()
if not bcrypt.checkpw(user_password.encode("utf-8"), result[1].encode("utf-8")):
    print("Error: Incorrect password")
    exit(1)
cursor.execute(
    "INSERT INTO Accesses (Date, Time, userID) VALUES (CURDATE(), CURTIME(), %s)", (user_id,))
my_db.commit()

print("Authentication successful")

server_identifier = config["General"]["ServerIdentifierShort"]
request_base_url = config["General"]["PanelURL"] + \
    "/api/client/servers/" + server_identifier + "/files"
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Authorization": "Bearer " + config["General"]["APIKey"]
}
whole_mod_size = 0
with open(config["General"]["IndexFilePath"], "r") as index_file:
    index = json.load(index_file)

index["additional"] = {}
for section in config.sections():
    if section == "General" or section == "Database":
        continue
    file_list = []
    exceptions = config[section]["Exceptions"].replace(" ", "").split(",")
    encoded_directory = quote(section)
    request_url = request_base_url + "/list?directory=" + encoded_directory
    response = requests.get(request_url, headers=headers)
    if response.status_code != 200:
        print("Error: " + response.text)
        exit(1)
    files = response.json()["data"]
    for file in files:
        if not file["attributes"]["is_file"] or file["attributes"]["name"] in exceptions:
            continue
        else:
            whole_mod_size += file["attributes"]["size"]
            request_url = request_base_url + "/download?file=" + \
                encoded_directory + "%2F" + quote(file["attributes"]["name"])
            file_download_link = requests.get(request_url, headers=headers)
            if file_download_link.status_code != 200:
                print("Error: " + file_download_link.text)
                exit(1)
            file_contents = requests.get(file_download_link.json(
            )["attributes"]["url"], headers=headers, allow_redirects=True)
            if file_contents.status_code != 200:
                print("Error: " + file_contents.text)
                exit(1)
            file_list.append({"name": file["attributes"]["name"],
                              "url": config["General"]["DownloadURLBase"] + section + "/" + file["attributes"]["name"],
                              "sha1": hl.sha1(file_contents.content).hexdigest(),
                              "sha256": hl.sha256(file_contents.content).hexdigest(),
                              "size": file["attributes"]["size"]})
            if not os.path.exists(config["General"]["DownloadDirectory"] + section):
                os.makedirs(config["General"]["DownloadDirectory"] + section)
            with open(config["General"]["DownloadDirectory"] + section + "/" + file["attributes"]["name"], "wb") as file:
                file.write(file_contents.content)
    index["additional"][section.replace("/", "", 1)] = file_list
index["wholeSize"] = whole_mod_size

optional_mod_list = []
request_url = request_base_url + "/list?directory=%2Fadditional-mods"
response = requests.get(request_url, headers=headers)
if response.status_code != 200:
    print(f"{request_url}\nError: " + response.text)
    exit(1)
files = response.json()["data"]
for file in files:
    if not file["attributes"]["is_file"]:
        continue
    else:
        request_url = request_base_url + "/download?file=%2Fadditional-mods%2F" + \
            quote(file["attributes"]["name"])
        file_download_link = requests.get(request_url, headers=headers)
        if file_download_link.status_code != 200:
            print(f"{request_url}\nError: " + file_download_link.text)
            exit(1)
        file_contents = requests.get(file_download_link.json(
        )["attributes"]["url"], headers=headers, allow_redirects=True)
        if file_contents.status_code != 200:
            print(f"{request_url}\nError: " + file_contents.text)
            exit(1)
        optional_mod_list.append({"name": file["attributes"]["name"],
                                  "url": config["General"]["DownloadURLBase"] + "/optionalMods/" + file["attributes"]["name"],
                                  "sha1": hl.sha1(file_contents.content).hexdigest(),
                                  "sha256": hl.sha256(file_contents.content).hexdigest(),
                                  "size": file["attributes"]["size"]})
        if not os.path.exists(config["General"]["DownloadDirectory"] + "/optionalMods"):
            os.makedirs(config["General"]
                        ["DownloadDirectory"] + "/optionalMods")
        with open(config["General"]["DownloadDirectory"] + "/optionalMods/" + file["attributes"]["name"], "wb") as file:
            file.write(file_contents.content)
index["optionalMods"] = optional_mod_list

with open(config["General"]["IndexFilePath"], "w") as index_file:
    json.dump(index, index_file)

print("Done")
exit(0)
