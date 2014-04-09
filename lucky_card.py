#!/usr/bin/env python3
# lucky_card.py - tweet a today's lucky DCD card
import requests
from PIL import Image
from io import BytesIO
from twython import Twython
from bs4 import BeautifulSoup
import re
from os.path import basename, dirname, splitext, exists
import yaml
import sys
from time import sleep
import random
from datetime.datetime import now

# settings
db_file = 'cards.yaml'
que_file = 'ques.yaml'
cred_file = '.credentials'
img_dir = 'img/'

def download(series_id=''):
    '''Download data from dcd site, and update database.'''
    # download card data
    site_url = 'http://precure-live.com/allstars/cardlist/'
    site_url_with_category = 'http://precure-live.com/allstars/cardlist/happiness.php?search=true&category='
    site_img_url_base = 'http://precure-live.com/allstars/image/cardlist/'
    if series_id:
        site_url = site_url_with_category + series_id
    if exists(db_file):
        with open(db_file, 'r+') as db:
            cards = yaml.load(db)
    else:
        cards = {}
    r = requests.get(site_url)
    site_card_list_url = r.url
    r.encoding = 'utf-8'  # prevent moji-bake
    soup = BeautifulSoup(r.text)
    site_cards = soup.find_all('table')[1:]
    for card in site_cards:
        series_name = basename(dirname(card.find_all('a')[0].img['src'])) # parent dirname i.e. 'happiness02'
        series_id = re.search(r'category=(\d+)', site_card_list_url).group(1) # 123456
        header = card.td.text.strip()
        series_text, no, no_max = re.search(r'(.+)(\d{2})/(\d{2})', header).groups() # i.e. 'ハピネスチャージ2だん キュアハニー登場 22/48'
        card_name = card.find(class_='cardname').text # 素敵なカードだよ
        model = card.find(class_='item').text         # 愛乃めぐみ
        img_front = basename(card.find_all('a')[0].img['src'])
        img_back = basename(card.find_all('a')[1].img['src'])
        img_both = splitext(img_front)[0] + '-both' + splitext(img_front)[1]
        cardtype = basename(card.find_all(class_='icon')[0].img['src'])
        if cardtype == 'img_dress_tops-hc.jpg':
            cardtype = 'dress-tops-hc'
        elif cardtype == 'img_dress_bottoms-hc.jpg':
            cardtype = 'dress-bottoms-hc'
        elif cardtype == 'ico_allstars.jpg':
            cardtype = 'allstars'
        rarity = basename(card.find_all(class_='icon')[1].img['src'])
        if rarity == 'img_rare_n-hc.gif':
            rarity = 'n-hc'
        elif rarity == 'img_rare_prc-hc.gif':
            rarity = 'prc-hc'
        card_text = card.find(class_='card_txt').text
        card_id = series_id + '-' + no # i.e. 123456-22
        if card_id in cards.keys():    # avoid double download
            print('This card has already downloaded. Skip.')
            continue
        else:
            cards[card_id] = {'series_name': series_name,
                                    'series_id': series_id,
                              'series_text': series_text,
                              'no': no,
                              'no_max': no_max,
                              'card_name': card_name,
                              'model': model,
                              'img_front': img_front,
                              'img_back': img_back,
                              'img_both': img_both,
                              'cardtype': cardtype,
                              'rarity': rarity,
                              'card_text': card_text}
        print('='*8)
        print('Get a new card.')
        print('='*8)
        print(cards[card_id])
        # download card img
        site_img_urls = [site_img_url_base + series_name + '/' + img_front,
                         site_img_url_base + series_name + '/' + img_back]
        imgs = []
        for site_img_url in site_img_urls:
            r = requests.get(site_img_url)
            imgs.append(Image.open(BytesIO(r.content)))
        w = sum(i.size[0] for i in imgs)
        mh = max(i.size[1] for i in imgs)
        res = Image.new("RGBA", (w,mh))
        x = 0
        for i in imgs:
            res.paste(i, (x, 0))
            x += i.size[0]
        res.save(img_dir + img_both)
        print('='*8)
        print('Download and concatenate two card image:', img_both)
        sleep(0.5)
        
    # write db
    with open(db_file, 'w') as db:
        db.write(yaml.dump(cards))

        
def shuffle():
    '''Create a list of shuffled cards to make a que file.'''
    with open(db_file) as f:
        cards = yaml.load(f)
    card_ids = list(cards.keys())
    random.shuffle(card_ids)
    que = []
    for card_id in card_ids:
        que.append({card_id: cards[card_id]})
    with open(que_file, 'w') as f:
        f.write(yaml.dump(que))

def tweet(status=''):
    '''Tweet a que.'''
    # twitter instance
    with open(cred_file) as f:
        app_key, app_secret, oauth_token, oauth_secret = \
                            [x.split()[0] for x in open('.credentials')]
    t = Twython(app_key, app_secret, oauth_token, oauth_secret)
    
    if status:  # manual tweet
        t.update_status(status=status)
    else:
        # read que
        with open(que_file) as f:
            que = yaml.load(f)
            card = que.pop(0).popitem() # => tuple(card_id, {...})
            card_id = card[0]
            img_path = card[1]['img_path']
            img_url = card[1]['img_url']
            model = card[1]['model']
            card_name = card[1]['card_name']
            card_text = card[1]['card_text']

        # generate status
        morning = now().hour < 16
        if morning:
            status = '今日のラッキーカードは、{model}の{cn}のカード！\
            「{ct}」今日がハッピーな一日になりますように…！'\
                .format(model=model, cn=card_name, ct=card_text)
        else:
            status = '今日のラッキーカードは、{model}の{cn}のカードでした。\
            今日はハッピーな一日にできたかな…？'\
                .format(model=model, cn=card_name, ct=card_text)
        
        # tweet
        if not img_url:
            img = open(img_path, 'rb')
            res = t.update_status_with_media(status=status, media=img)
            img_url = res['entities']['media'][0]['url']
            # update db
            with open(db_file) as db:
                cards = yaml.load(db)
                cards[card_id]['img_url'] = img_url
                db.write(yaml.dump(cards))
        else:
            status += ' ' + img_url
            res = t.update_status(status=status)
        
        # write que
        if len(que) == 0: # que list is empty
            shuffle()  # make new que
        elif not morning:
            with open(que_file, 'w') as f:
                f.write(yaml.dump(que))

if __name__ == '__main__':
    usage = '''\
usage: {0} <command> [<args>]
command:
  download [<series_id>]  Download cards data and images from the site.
  tweet [<status>]       Tweet a que[status].
  shuffle                 Generate a shuffled que list.'''.format(basename(sys.argv[0]))
    if len(sys.argv) == 1:
        print(usage)
    else:
        if sys.argv[1] == 'download':
            if len(sys.argv) > 2:
                series_id = sys.argv[2]
                download(series_id)
            else:
                download()
        elif sys.argv[1] == 'tweet':
            if len(sys.argv) > 2:
                tweet(sys.argv[2])
            else:
                tweet()
        elif sys.argv[1] == 'shuffle':
            shuffle()
