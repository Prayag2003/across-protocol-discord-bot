from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from textblob import TextBlob
import re
from typing import List, Set
from loguru import logger   

class Web3QueryPreprocessor:
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        
        # Common Web3 terms that shouldn't be corrected
        self.web3_terms = {
            'eth', 'gwei', 'wei', 'dao', 'defi', 'dex', 'nft', 'hodl', 
            'blockchain', 'metamask', 'wallet', 'gas', 'mint', 'token',
            'smart', 'contract', 'block', 'hash', 'tx', 'txn', 'transaction',
            'wen', 'gm', 'wagmi', 'ngmi', 'dyor', 'fud', 'fomo', 'rekt'
        }
        
        # Load standard English stop words but remove some that might be important
        self.stop_words = set(stopwords.words('english')) - {
            'how', 'when', 'where', 'what', 'why', 'which',  # Question words
            'not', 'no', 'nor',  # Negations
            'up', 'down',  # Price movements
            'in', 'out',  # Transaction directions
            'to', 'from'  # Transfer directions
        }
        
        # Common Web3 abbreviations
        self.abbreviations = {
            'tx': 'transaction',
            'txn': 'transaction',
            'msg': 'message',
            'addr': 'address',
            'sig': 'signature',
            'auth': 'authentication',
            'amt': 'amount',
            'bal': 'balance'
        }

    def expand_abbreviations(self, text: str) -> str:
        """Expand common Web3 abbreviations"""
        words = text.split()
        return ' '.join(self.abbreviations.get(word.lower(), word) for word in words)

    def correct_spelling(self, text: str) -> str:
        """Correct spelling while preserving Web3 terminology"""
        words = text.split()
        corrected_words = []
        
        for word in words:
            if word.lower() in self.web3_terms:
                corrected_words.append(word)
                continue
                
            blob = TextBlob(word)
            corrected = str(blob.correct())
            corrected_words.append(corrected)
                
        return ' '.join(corrected_words)

    def normalize_text(self, text: str) -> str:
        """Normalize text by removing special characters"""
        text = re.sub(r'[^a-zA-Z0-9\s\-_./]', ' ', text)
        return ' '.join(text.split()).lower()

    def lemmatize_text(self, text: str) -> str:
        """Lemmatize text while preserving Web3 terms"""
        words = word_tokenize(text)
        lemmatized_words = []
        
        for word in words:
            if word.lower() in self.web3_terms:
                lemmatized_words.append(word)
            else:
                lemmatized_words.append(self.lemmatizer.lemmatize(word))
                
        return ' '.join(lemmatized_words)

    def remove_stop_words(self, text: str) -> str:
        """Remove stop words while preserving question structure"""
        words = text.split()
        return ' '.join(word for word in words if word.lower() not in self.stop_words)

    def preprocess(self, query: str) -> str:
        """Main preprocessing pipeline"""

        query = self.expand_abbreviations(query)
        query = self.normalize_text(query)
        query = self.correct_spelling(query)        
        query = self.lemmatize_text(query)        
        query = self.remove_stop_words(query)
        logger.info(f"Preprocessed query: {query.strip()}")
        
        return query.strip()