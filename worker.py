# encoding: utf-8

import os
import json
import re
import datetime
import time
import random
import sys
from urllib.error import HTTPError

import requests
import pymongo
import xmltodict
from bottlenose import api
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.keys import Keys

from credentials import *

headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'}

search_indexes = [
    'All', # 全て
    'Beauty', # コスメ
    'Grocery', # 食品
    'Industrial',
    'PetSupplies',
    'OfficeProducts',
    'CreditCards',
    'Electronics', # エレクトロニクス
    'Watches', # 時計
    'Jewelry', # ジュエリー
    'MobileApps',
    'Shoes',
    'KindleStore',
    'Automotive',
    'Pantry',
    'MusicalInstruments',
    'GiftCards',
    'Toys', # おもちゃ
    'VideoDownload',
    'SportingGoods', # スポーツ＆アウトドア
    'PCHardware',
    'Books', # 本(和書)
    'VHS', # VHS
    'MP3Downloads',
    'Baby', # ベビー＆マタニティ
    'MusicTracks', # 曲名
    'Hobbies', # ホビー
    'VideoGames', # ゲーム
    'ForeignBooks', # 洋書
    'Apparel', # アパレル
    'Marketplace',
    'DVD', # DVD
    'HomeImprovement',
    'Appliances',
    'Kitchen', # ホーム＆キッチン
    'Music', # ミュージック
    'Video', # ビデオ
    'Blended', # 全て
    'HealthPersonalCare', # ヘルスケア
    'Classical', # クラシック音楽
    'Software' # ソフトウェア
]

def error_handler(err):
    ex = err['exception']
    # if isinstance(ex, HTTPError) and ex.code == 503:
    #     print('===========503===========')
    #     time.sleep(1) # 1秒待つ
    #     return True
    if isinstance(ex, HTTPError):
        print('==========={}==========='.format(ex.code))
        time.sleep(1) # 1秒待つ
        return True

class Amazon(object):

    api = api.Amazon(AMAZON_ACCESS_KEY, AMAZON_SECRET_KEY, AMAZON_ASSOC_TAG, Region="JP", ErrorHandler=error_handler)

    def __init__(self):
        self.init_db()

    def init_db(self):
        client = pymongo.MongoClient(DB_HOST, DB_PORT)
        db = client[DB_NAME]
        self.co = db.amazon
        self.cod = db.amazon_detail
        self.coe = db.amazon_error

    def crawler(self, url):
        self.f = open('log.txt', 'w')
        self.chro = webdriver.Chrome('./chromedriver')
        self.chro.get(url)
        urls = self.chro.find_elements_by_css_selector('.categoryRefinementsSection .forExpando li:not(.shoppingEngineExpand) a')
        urls = [u.get_attribute('href') for u in urls]
        urls2 = self.chro.find_elements_by_css_selector('.seeAllSmartRefDepartmentOpen li:not(#fewDep) a')
        urls2 = [u.get_attribute('href') for u in urls2]
        urls = urls + urls2
        print('got url')
        self.f.write('==================================================\n')
        for u in urls:
            self.f.write(u + '\n')
        self.f.write('==================================================\n')
        for u in urls:
            self.crawl_page(u)
        self.chro.close()

    def crawl_page(self, url=None):
        if url:
            self.f.write(url + '\n')
            self.chro.get(url)
        items = self.chro.find_elements_by_css_selector('.s-result-item.celwidget')
        for i in items:
            try:
                asin = i.get_attribute('data-asin')
                title = i.find_element_by_css_selector('a.s-color-twister-title-link').get_attribute('title')
                url = i.find_element_by_css_selector('a.s-color-twister-title-link').get_attribute('href')
                img = i.find_element_by_css_selector('img.s-access-image').get_attribute('src')
                rate_val = None
                rate_num = None
                star = i.find_element_by_css_selector('.a-icon-star .a-icon-alt')
                if star:
                    rate_str = star.get_attribute('innerHTML')
                    m = re.search('5つ星のうち ([0-9]*\.?[0-9]*)', rate_str)
                    if m:
                        if m.group(1) not in ['', '.']:
                            rate_val = float(m.group(1))
                    parent = star.find_element_by_xpath('..')
                    while parent and parent.tag_name != 'div':
                        parent = parent.find_element_by_xpath('..')
                    if parent:
                        a = parent.find_element_by_xpath('a')
                        if a:
                            num_str = a.get_attribute('innerHTML')
                            if num_str != '':
                                rate_num = int(num_str)
                print(asin, title, rate_val, rate_num)
                self.f.write(asin + ',' + title + '\n')
                data = {
                    '_id': asin,
                    'title': title,
                    'img': img,
                    'url': url
                }
                if rate_val:
                    data['rate_val'] = rate_val
                if rate_num:
                    data['rate_num'] = rate_num
                self.to_db(data)
            except:
                pass
        next_a = self.chro.find_elements_by_css_selector('a.pagnNext')
        if next_a:
            # print(next_a[0].text)
            # self.chro.find_element_by_xpath('//body').send_keys(Keys.END)
            # next_a[0].click()
            # self.f.write('click\n')
            next_url = next_a[0].get_attribute('href')
            self.crawl_page(next_url)
        else:
            return

    def get_detail(self):
        res = self.co.find({'geted': {'$ne':True}})
        for r in res:
            asin = r['_id']
            in_db = self.cod.find_one({'_id': asin})
            if in_db:
                continue
            in_db = self.coe.find_one({'_id': asin})
            if in_db:
                continue

            print(asin, r['title'])
            detail = self.item(asin)
            try:
                self.cod.insert(dict(detail['ItemLookupResponse']['Items']['Item'], **{'_id': asin}))
                self.co.update_one({'_id': asin}, {'$set': {'geted': True}})
            except Exception as e:
                # print("例外args:", e.args)
                # print(detail)
                # print(json.dumps(detail, ensure_ascii=False, indent=2))
                if 'Errors' in detail['ItemLookupResponse']['Items'].get('Request', {}):
                    print('@@@@@@@@@Error@@@@@@@@')
                    self.coe.insert(dict(detail['ItemLookupResponse']['Items']['Request']['Errors'], **{'_id': asin}))
                else:
                    print("例外args:", e.args)
            # break
            time.sleep(1.2)


    def search(self, keywords, search_index="All", item_page=1):
        res = self.api.ItemSearch(SearchIndex=search_index, Keywords=keywords, ItemPage=item_page, ResponseGroup="Large", MinimumPrice=10000, MaximumPrice=20000)
        self.parse(res)

    def item(self, item_id):
        data = self.api.ItemLookup(ItemId=item_id, ResponseGroup="Large")
        # f = open('item.txt', 'w')
        # f.write(res.decode("utf-8"))
        return xmltodict.parse(data.decode("utf-8"))

    def parse(self, data):
        # soup = BeautifulSoup(data)
        # f = open('test.txt', 'w')
        # f.write(json.dumps(xmltodict.parse(data.decode("utf-8"))))
        _data = xmltodict.parse(data.decode("utf-8"))
        print(_data)
        print(_data['ItemSearchResponse']['Items']['TotalResults'])

    def to_db(self, data):
        # in_db = self.co.find_one({'_id': data['_id']})
        # if not in_db:
        self.co.update_one({'_id': data['_id']}, {'$set': data}, upsert=True)
        if 'rate_val' in data and self.cod.find_one({'_id': data['_id']}):
            self.cod.update_one({'_id': data['_id']}, {'$set': {
                    'rate_val': data['rate_val'],
                    'rate_num': data.get('rate_num')
                }})
        # for user in data:
        #     now = datetime.datetime.now()
        #     user['_id'] = user.pop('id')
        #     print(user['nickname'], user['tweet'])
        #     in_db = self.co.find_one({'_id': user['_id']})
        #     res = {}
        #     if in_db:
        #         res['images'] = self.process_images(in_db['images'], user.pop('images'))
        #         if in_db['tweet'] != user['tweet']:
        #             in_db['tweets'].insert(0, {
        #                 'tweet': user['tweet'],
        #                 'created': now
        #                 })
        #             res['tweets'] = in_db['tweets']
        #         if in_db['introduction'] != user['introduction']:
        #             in_db['introductions'].insert(0, {
        #                 'introduction': user['introduction'],
        #                 'created': now
        #                 })
        #             res['introductions'] = in_db['introductions']
        #         for k, v in user.items():
        #             res[k] = v
        #         res['updated'] = now
        #     else:
        #         res = user
        #         res['tweets'] = [{
        #                 'tweet': res['tweet'],
        #                 'created': now
        #             }]
        #         res['introductions'] = [{
        #                 'introduction': res['introduction'],
        #                 'created': now
        #             }]
        #         res['images'] = self.process_images([], res['images'])
        #         res['created'] = now
        #     self.co.update_one({'_id': res['_id']}, {'$set': res}, upsert=True)


if __name__ == '__main__':
    amz = Amazon()
    # amz.search(keywords='台湾', search_index="Kitchen", item_page=1)
    # amz.item('B015SVCALW')
    for url in [
        'https://www.amazon.co.jp/s/ref=nb_sb_noss_2?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dkitchen&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss_2?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dcomputers&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss_2?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Delectronics&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Doffice-products&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss_2?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dpets&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dhpc&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dbeauty&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dluxury-beauty&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dbaby&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dfashion&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dapparel&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dshoes&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dwatch&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Djewelry&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dtoys&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dhobby&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dmi&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dsporting&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dautomotive&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Ddiy&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dappliances&field-keywords=%E5%8F%B0%E6%B9%BE',
        'https://www.amazon.co.jp/s/ref=nb_sb_noss?__mk_ja_JP=%E3%82%AB%E3%82%BF%E3%82%AB%E3%83%8A&url=search-alias%3Dindustrial&field-keywords=%E5%8F%B0%E6%B9%BE'
    ]:
        amz.crawler(url)
    # amz.get_detail()
