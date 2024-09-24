import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from urllib.parse import parse_qs, urlparse
import json
import pandas as pd
from datetime import datetime
import uuid
import csv
import os
from typing import Callable, Any
from wsgiref.simple_server import make_server

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)

adj_noun_pairs_count = {}
sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

reviews = pd.read_csv('data/reviews.csv').to_dict('records')
locations_list = [
    "Albuquerque, New Mexico",
    "Carlsbad, California",
    "Chula Vista, California",
    "Colorado Springs, Colorado",
    "Denver, Colorado",
    "El Cajon, California",
    "El Paso, Texas",
    "Escondido, California",
    "Fresno, California",
    "La Mesa, California",
    "Las Vegas, Nevada",
    "Los Angeles, California",
    "Oceanside, California",
    "Phoenix, Arizona",
    "Sacramento, California",
    "Salt Lake City, Utah",
    "Salt Lake City, Utah",
    "San Diego, California",
    "Tucson, Arizona"
]
# Remove duplicates if any
locations_list = list(dict.fromkeys(locations_list))

class ReviewAnalyzerServer:
    def __init__(self) -> None:
        # This method is a placeholder for future initialization logic
        self.location = ''
        self.start_date = ''
        self.end_date = ''
        self.review_body = ''
        pass

    def analyze_sentiment(self, review_body):
        sentiment_scores = sia.polarity_scores(review_body)
        return sentiment_scores

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> bytes:
        """
        The environ parameter is a dictionary containing some useful
        HTTP request information such as: REQUEST_METHOD, CONTENT_LENGTH, QUERY_STRING,
        PATH_INFO, CONTENT_TYPE, etc.
        """
        # Get a copy of the reviews list
        reviewsCopy = reviews.copy()

        # Get the query string from the environ dictionary
        Query = environ.get('QUERY_STRING', '')

        if environ["REQUEST_METHOD"] == "GET":
            # Create the response body from the reviews and convert to a JSON byte string
            #response_body = json.dumps(reviews, indent=2).encode("utf-8")
            
            # Write your code here
            def add_sentiment_to_each_review(reviews_list):
                for review in reviews_list:
                    review['sentiment'] = self.analyze_sentiment(review['ReviewBody'])
                return reviews_list
            
            def get_query_parameters(Query):
                parameters = Query.split('&')
                Query = {parameter.split('=')[0]: parameter.split('=')[1] if '=' in parameter else '' for parameter in parameters}
                if 'location' in Query:
                    Query['location'] = Query['location'].replace("+", " ").replace("%2C", ",")
                    self.location = Query['location']
                else:
                    self.location = ''
                if 'start_date' in Query:
                    self.start_date = Query['start_date']
                else:
                    self.start_date = ''
                if 'end_date' in Query:
                    self.end_date = Query['end_date']
                else:
                    self.end_date = ''

            get_query_parameters(Query)
            
            # Filter reviews based on location
            if self.location in locations_list:
                for review in reviewsCopy[:]:
                    if review['Location'] != self.location:
                        reviewsCopy.remove(review)
            
            # Filter reviews based on start_date
            if self.start_date != '':
                _start_date = datetime.strptime(self.start_date, '%Y-%m-%d')
                print(_start_date)
                for review in reviewsCopy[:]:
                    if datetime.strptime(review['Timestamp'].split(' ')[0], '%Y-%m-%d') <= _start_date:
                        reviewsCopy.remove(review)
            
            # Filter reviews based on end_date
            if self.end_date != '':
                _end_date = datetime.strptime(self.end_date, '%Y-%m-%d')
                print(_end_date)
                for review in reviewsCopy[:]:
                    if datetime.strptime(review['Timestamp'].split(' ')[0], '%Y-%m-%d') >= _end_date:
                        reviewsCopy.remove(review)
            
            reviewsCopy = add_sentiment_to_each_review(reviewsCopy)
            
            def order_descending_by_sentiment(reviews_list):
                def get_compound_value(item):
                    return item["sentiment"]["compound"]
                return sorted(reviews_list, key=get_compound_value, reverse=True)
            
            reviewsCopy = order_descending_by_sentiment(reviewsCopy)

            response_body = json.dumps(reviewsCopy, indent=2).encode("utf-8")

            # Set the appropriate response headers
            start_response("200 OK", [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(response_body)))
             ])
            
            return [response_body]


        if environ["REQUEST_METHOD"] == "POST":
            try:
                # Write your code here

                # Read the POST request
                request_body = environ['wsgi.input'].read(int(environ.get('CONTENT_LENGTH'))).decode('utf-8')
                
                # Get the location and review body parameters from the request body
                parameters = dict(parameter.split('=') for parameter in request_body.split('&'))
                if 'Location' in parameters:
                    self.location = parameters['Location'].strip()
                    self.location = self.location.replace("+", " ").replace("%2C", ",")
                else:
                    self.location = ''
                if 'ReviewBody' in parameters:
                    self.review_body = parameters['ReviewBody'].strip()
                    self.review_body = self.review_body.replace("+", " ").replace("%21", "!")
                else:
                    self.review_body = ''
                
                # Validate parameters
                if self.location == '' or self.review_body == '':
                    raise ValueError("Missing 'Location' or 'ReviewBody'")

                # This means that the location is not in the locations_list
                if self.location not in locations_list:
                    response_body = json.dumps({
                        'status': 'error',
                        'message': 'Invalid location'
                        }).encode('utf-8')
                    start_response("400 Bad Request", [
                        ("Content-Type", "application/json"),
                        ("Content-Length", str(len(response_body)))
                        ])
                    return [response_body]

                # Add the new review to the reviews list
                new_review = {
                        "ReviewId": str(uuid.uuid4()),
                        "Location": self.location,
                        "Timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "ReviewBody": self.review_body
                    }
                    
                # Add the new review to the reviews list
                reviews.append(new_review)

                # Write the reviews to the CSV file
                with open('data/reviews.csv', 'a', newline='') as csvfile:
                    #csvfile.write('\n')
                    fieldnames = ["ReviewId", "Location", "Timestamp", "ReviewBody"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    # Append the new review to the CSV file
                    writer.writerow(new_review)

                # Create a response
                response_body = json.dumps(new_review).encode('utf-8')
                
                # Send response headers
                start_response("201 Review is added successfully to the csv file!", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(response_body)))
                ])
                # Return the response body
                return [response_body]
            except ValueError as e:
                # Handle missing parameters
                response_body = json.dumps({
                    'status': 'missing parameter',
                    'message': str(e)
                }).encode('utf-8')
                
                start_response("400 Bad Request", [
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(response_body)))
                ])
                return [response_body]

if __name__ == "__main__":
    app = ReviewAnalyzerServer()
    port = os.environ.get('PORT', 8000)
    with make_server("", port, app) as httpd:
        print(f"Listening on port {port}...")
        httpd.serve_forever()