#!/usr/bin/env python3
# lucky_card.py - tweet a today's lucky DCD card
import re
from os.path import basename, dirname, splitext, exists
import yaml
import sys
from time import sleep
import random
from datetime import datetime
from dateutil import parser
import requests
from PIL import Image
from twython import Twython
from bs4 import BeautifulSoup

# settings
db_file = 'cards.yaml'
que_file = 'ques.yaml'
log_file = 'tweet.log'
img_dir = 'img/'
cred_file = '.credentials'

site_url = 'http://precure-live.com/allstars/cardlist/'
site_url_with_category = 'http://precure-live.com/allstars/cardlist/happiness.php?search=true&category='
site_img_url_base = 'http://precure-live.com/allstars/image/cardlist/'

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
    new_cardlist = []
    for card in site_cards:
        series_name = basename(dirname(card.find_all('a')[0].img['src'])) # parent dirname i.e. 'happiness02'
        series_id = re.search(r'category=(\d+)', site_card_list_url).group(1) # 123456
        header = card.td.text.strip()
        match = re.search(r'(.+)(\d{2})/(\d{2})', header) # i.e. 'ハピネスチャージ2だん キュアハニー登場 22/48'
        if match:
            series_text, no, no_max = match.groups()
        else: # promo card
            match = re.search(r'(.+)(\d{2})', header) # i.e. 'ハピネスチャージプロモ01'
            series_text, no, no_max = match.group(1), match.group(2), 'promo'
        card_name = card.find(class_='cardname').text # 花がらドレス
        model = card.find(class_='item').text         # 愛乃めぐみ
        img_front = series_id + '-' + basename(card.find_all('a')[0].img['src'])
        img_back = series_id + '-' + basename(card.find_all('a')[1].img['src'])
        img_both = splitext(img_front)[0][:-2] + '-w' + splitext(img_front)[1]
        cardtype = basename(card.find_all(class_='icon')[0].img['src'])
        if cardtype == 'img_dress_tops-hc.jpg':
            cardtype = 'dress-tops-hc'
        elif cardtype == 'img_dress_bottoms-hc.jpg':
            cardtype = 'dress-bottoms-hc'
        elif cardtype == 'ico_allstars.jpg':
            cardtype = 'allstars'
        rarity_icon = card.find_all(class_='icon')[1].img
        if rarity_icon:
            rarity = basename(rarity_icon['src'])
            if rarity == 'img_rare_n-hc.gif':
                rarity = 'n-hc'
            elif rarity == 'img_rare_prc-hc.gif':
                rarity = 'prc-hc'
        else: # promo card
            rarity = False

        card_text = card.find(class_='card_txt').text # 素敵なカードだよ
        card_id = series_id + '-' + no # i.e. 123456-22
        if card_id in cards.keys():    # avoid double download
            # print('This card has already downloaded. Skip. :', card_id, card_name)
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
                              'img_url': False,
                              'cardtype': cardtype,
                              'rarity': rarity,
                              'card_text': card_text}
        print('Get a new card.')
        print(cards[card_id])

        filenames = [img_front, img_back]
        for filename in filenames:
            img_url = site_img_url_base + series_name + '/' + filename[7:]
            r = requests.get(img_url)
            with open(img_dir + filename, 'wb') as f:
                f.write(r.content)

        img_concatenate(img_front, img_back, img_both)

        # add to new_cardlist
        new_cardlist.append('{}「{}」'.format(model, card_name))
        
        print('Download and concatenamhte images:', img_both)
        print('='*8)
        sleep(0.5)
        
    # write db
    with open(db_file, 'w') as db:
        yaml.dump(cards, db)
    if not test and new_cardlist:
        tweet('カードリスト ({}) が更新されました！ 追加されたのは次の{}枚のカードです。'.format(site_url, len(new_cardlist)))
        new_cardlist = ' / '.join(new_cardlist)
        new_cardlists = []
        while len(new_cardlist) > 0:
            new_cardlists.append(new_cardlist[:140])
            new_cardlist = new_cardlist[140:]
        for card in new_cardlists:
            tweet(card)
            sleep(1)
        shuffle()
        
def img_concatenate(front, back, both):
    '''concatenate front and back images and save to both'''
    img_front = Image.open(img_dir + front)
    img_back = Image.open(img_dir + back)
        
    w = img_front.size[0] * 2 + 10
    h = img_front.size[1]
    img_both = Image.new("RGBA", (w, h))
    x = 0
    img_both.paste(img_front, (x, 0))
    x += img_front.size[0] + 10
    img_both.paste(img_back, (x, 0))
    img_both.save(img_dir + 'both/' + both)

def redownload():
    '''re-download all the images'''
    with open(db_file) as db:
        cards = yaml.load(db)
    for (id, card) in cards.items():
        img_front = card['img_front']
        img_back = card['img_back']
        img_both = card['img_both']
        for img in (img_front, img_back):
            img_url = site_img_url_base + card['series_name'] + '/' + img[7:]
            r = requests.get(img_url)
            with open(img_dir + img, 'wb') as f:
                f.write(r.content)
        img_concatenate(img_front, img_back, img_both)
        print('Donwload and concatenate both images:', img_both)
        sleep(0.5)

def shuffle():
    '''Generate a shuffled que list.'''
    with open(db_file) as db:
        cards = yaml.load(db)
    card_ids = list(cards.keys())
    random.shuffle(card_ids)
    ques = []
    for card_id in card_ids:
        ques.append(card_id)
    with open(que_file, 'w') as q:
        yaml.dump(ques, q)

def tweet(status=''):
    '''Tweet a que.'''
    # twitter instance
    with open(cred_file) as f:
        app_key, app_secret, oauth_token, oauth_secret = \
                            [x.strip() for x in f]
    t = Twython(app_key, app_secret, oauth_token, oauth_secret)
    
    if status: # manual tweet
        t.update_status(status=status)
    else:
        # read que
        with open(que_file) as q:
            que = yaml.load(q)
        card_id = que[0]
        with open(db_file) as db:
            cards = yaml.load(db)
        card = cards[card_id]
        img_both = card['img_both']
        model = card['model']
        card_name = card['card_name']
        card_text = card['card_text']

        # generate status
        morning = datetime.now().hour < 16
        if morning:
            if model == card_name:
                status = '今日のラッキーカードは、{model}のカードです！\
今日がハッピーな一日になりますように！'.format(model=model, ct=card_text)
            else:
                status = '今日のラッキーカードは、{model}の「{cn}」のカードです！\
「{ct}」今日がハッピーな一日になりますように！'.format(model=model, cn=card_name, ct=card_text)
        else:
            if model == card_name:
                status = '今日も一日お疲れさま！今日のラッキーカードは、{model}のカードでした。\
ハッピーな一日にできたかな？'.format(model=model)
            else:
                status = '今日も一日お疲れさま！今日のラッキーカードは、{model}の「{cn}」のカードでした。\
ハッピーな一日にできたかな？'.format(model=model, cn=card_name)

        # tweet
        if card['img_url']:
            status += ' ' + card['img_url']
            res = t.update_status(status=status)
        else:
            img = open(img_dir + 'both/' + img_both, 'rb')
            res = t.update_status_with_media(status=status, media=img)
            img_url = res['entities']['media'][0]['url']
            # add img_url to db
            if not test:
                with open(db_file) as db:
                    cards = yaml.load(db)
                    cards[card_id]['img_url'] = img_url
                with open(db_file, 'w') as db:
                    yaml.dump(cards, db)

        # on the evening, pop ques and check new card list
        if not morning and not test:
            with open(que_file) as q:
                ques = yaml.load(q)
            ques.pop(0)
            with open(que_file, 'w') as q:
                yaml.dump(ques, q)
            if len(ques) == 0: # que list is empty
                shuffle()  # make new que

        # write tweet status log
        time = parser.parse(res['created_at']).astimezone()
        time = datetime.strftime(time, '%Y-%m-%d %H:%M:%S')
        status = res['text']
        log_text = ','.join([time,str(test),card_id,status]) + '\n'
        print('Tweet:', log_text)
        with open(log_file, 'a') as log:
            log.write(log_text)
                
def clear():
    '''Clear img_url to re-upload image files.'''
    with open(db_file) as db:
        cards = yaml.load(db)
    for (id, card) in cards.items():
        card['img_url'] = False
    with open(db_file, 'w') as db:
        yaml.dump(cards, db)
                
if __name__ == '__main__':
    usage = '''\
usage: {0} [test] <command> [<args>]
command:
  download [<series_id>]  {1}
  tweet [<status>]        {2}
  redownload              {3}
  shuffle                 {4}
  clear                   {5}
test:
  if 'test' is given as the first argument, post tweet to the test account.'''.format(
          basename(sys.argv[0]),
          download.__doc__,
          tweet.__doc__,
          redownload.__doc__,
          shuffle.__doc__,
          clear.__doc__,)

    if len(sys.argv) == 1:
        print(usage)
    else:
        if sys.argv[1] == 'test':
            test = True
            cred_file = '.credentials_for_test'
            sys.argv.pop(1)
        else:
            test = False
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
        elif sys.argv[1] == 'redownload':
            redownload()
        elif sys.argv[1] == 'shuffle':
            shuffle()
        elif sys.argv[1] == 'clear':
            clear()
