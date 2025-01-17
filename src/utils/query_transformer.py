from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from textblob import TextBlob
import re
from typing import List, Set
import spacy

class Web3QueryPreprocessor:
    def __init__(self):
        # Initialize spacy for better entity recognition
        self.nlp = spacy.load('en_core_web_sm')
        self.lemmatizer = WordNetLemmatizer()
        
        # Common Web3 terms that shouldn't be corrected
        self.web3_terms = {
            'eth', 'gwei', 'wei', 'dao', 'defi', 'dex', 'nft', 'hodl', 
            'blockchain', 'metamask', 'wallet', 'gas', 'mint', 'token',
            'smart', 'contract', 'block', 'hash', 'tx', 'txn', 'transaction',
            'wen', 'gm', 'wagmi', 'ngmi', 'dyor', 'fud', 'fomo', 'rekt',
            'sol', 'btc', 'staking', 'yield', 'apy', 'apr', 'bridge',
            'layer', 'l1', 'l2', 'rollup', 'mainnet', 'testnet'
        }
        
        # Load standard English stop words but remove some that might be important
        # in crypto context
        self.stop_words = set(stopwords.words('english')) - {
            'how', 'when', 'where', 'what', 'why', 'which',  # Question words
            'not', 'no', 'nor',  # Negations
            'up', 'down',  # Price movements
            'in', 'out',  # Transaction directions
            'to', 'from'  # Transfer directions
        }
        
        # Common Web3 abbreviations and their expansions
        self.abbreviations = {
            'tx': 'transaction',
            'txn': 'transaction',
            'msg': 'message',
            'addr': 'address',
            'sig': 'signature',
            'auth': 'authentication',
            'amt': 'amount',
            'bal': 'balance',
            'max': 'maximum',
            'min': 'minimum',
            'conf': 'confirmation',
            'recv': 'receive',
            'rcv': 'receive',
            'sent': 'send',
            'val': 'value',
            'ver': 'version',
            'pw': 'password',
            'pw': 'password',
            'amt': 'amount',
            'addr': 'address'
        }

    def expand_abbreviations(self, text: str) -> str:
        """Expand common Web3 abbreviations"""
        words = text.split()
        return ' '.join(self.abbreviations.get(word.lower(), word) for word in words)

    def correct_spelling(self, text: str) -> str:
        """
        Correct spelling while preserving Web3 terminology
        """
        words = text.split()
        corrected_words = []
        
        for word in words:
            # Don't correct Web3 terms
            if word.lower() in self.web3_terms:
                corrected_words.append(word)
                continue
                
            # Use TextBlob for spell correction
            blob = TextBlob(word)
            corrected = str(blob.correct())
            
            # If the correction confidence is high enough, use it
            if word.lower() != corrected.lower():
                corrected_words.append(corrected)
            else:
                corrected_words.append(word)
                
        return ' '.join(corrected_words)

    def normalize_text(self, text: str) -> str:
        """
        Normalize text by removing special characters and extra whitespace
        """
        # Remove special characters but keep important symbols
        text = re.sub(r'[^a-zA-Z0-9\s\-_./]', ' ', text)
        # Normalize whitespace
        text = ' '.join(text.split())
        return text.lower()

    def lemmatize_text(self, text: str) -> str:
        """
        Lemmatize text while preserving Web3 terms
        """
        doc = self.nlp(text)
        lemmatized_words = []
        
        for token in doc:
            # Don't lemmatize Web3 terms
            if token.text.lower() in self.web3_terms:
                lemmatized_words.append(token.text)
            else:
                lemmatized_words.append(self.lemmatizer.lemmatize(token.text))
                
        return ' '.join(lemmatized_words)

    def remove_stop_words(self, text: str) -> str:
        """
        Remove stop words while preserving question structure
        """
        words = text.split()
        return ' '.join(word for word in words if word.lower() not in self.stop_words)

    def preprocess(self, query: str) -> str:
        """
        Main preprocessing pipeline
        """
        # Expand common abbreviations
        query = self.expand_abbreviations(query)
        
        # Normalize text
        query = self.normalize_text(query)
        
        # Correct spelling while preserving Web3 terms
        query = self.correct_spelling(query)
        
        # Lemmatize
        query = self.lemmatize_text(query)
        
        # Remove stop words
        query = self.remove_stop_words(query)
        
        return query.strip()