# encoding: utf-8

import os
import datetime

import requests
import pymongo
import tornado.ioloop
import tornado.web

from credentials import *

client = pymongo.MongoClient(DB_HOST, DB_PORT)
db = client[DB_NAME]
# db.authenticate(DB_USERNAME, DB_PW)
co = db.amazon_detail

def result_parse(data):
    for k, v in data.items():
        if type(v) == dict:
            data[k] = result_parse(v)
        elif type(v) == list:
            data[k] = [result_parse(x) for x in v]
        elif type(v) == datetime.datetime:
            data[k] = v.strftime(format('%Y-%m-%d %H:%M:%S.%f'))
        elif type(v) == datetime.date:
            data[k] = v.strftime(format('%Y-%m-%d'))
    return data

class MainHandler(tornado.web.RequestHandler):


    def set_default_headers(self):
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET,PUT,POST,OPTIONS")
        self.set_header("Access-Control-Allow-Headers",
                        "Content-Type, Depth, User-Agent, X-File-Size, X-Requested-With, X-Requested-By,If-Modified-Since, X-File-Name, Cache-Control")

    def options(self):
        # no body
        self.set_status(204)
        self.finish()

    def get(self):
        path = self.request.path
        event = {
            'queryParams': {k: v[0].decode("utf-8") for k, v in self.request.arguments.items()},
            'path': path,
            'body': '',
            'method': 'GET'
        }
        # print('get',event['queryParams'].get('gt', '2017-10-1 00:00:00.0'))
        limit = int(event['queryParams'].get('limit', 2))
        offset = int(event['queryParams'].get('offset', 0))
        
        _or = []
        if 'title' in event['queryParams']:
            _or.append({
                'ItemAttributes.Title': {'$regex': event['queryParams']['title']}
            })
        if 'editorial' in event['queryParams']:
            _or.append({
                'EditorialReviews.EditorialReview.Content': {'$regex': event['queryParams']['editorial']}
            })
        if 'feature' in event['queryParams']:
            _or.append({
                'ItemAttributes.Feature': {'$regex': event['queryParams']['feature']}
            })

        query = {
            'dislike': None,
            '$or': _or
        }

        # print('query', query)
        # for x in co.find(query).limit(limit):
        #     print(x)
        try:
            # results = [result_parse(x) for x in co.find(query).limit(limit)]
            results = [x for x in co.find(query).limit(limit).skip(offset)]
            self.write({
                "status": 'success',
                "results": results
            })
            print('{}/{}'.format(offset, co.find(query).count()))

        except Exception as e:
            self.write({
                "status": 'error',
                "msg": e.args
            })

    def put(self):
        path = self.request.path
        body = tornado.escape.json_decode(self.request.body)

        print('path', path)

        if path == '/dislike':
            try:
                co.update_one({'_id': body['_id']}, {'$set': {'dislike': True}})
                self.write({
                    "status": 'success'
                })
            except Exception as e:
                self.write({
                    "status": 'error',
                    "msg": e.args
                })
        elif path == '/favorite':
            try:
                co.update_one({'_id': body['_id']}, {'$set': {'favorite': True}})
                self.write({
                    "status": 'success'
                })
            except Exception as e:
                self.write({
                    "status": 'error',
                    "msg": e.args
                })

application = tornado.web.Application([
    (r"/.*", MainHandler)
], static_path=os.path.join(os.getcwd(),  "static"), debug=True)

if __name__ == "__main__":
    application.listen(8891)
    tornado.ioloop.IOLoop.instance().start()
