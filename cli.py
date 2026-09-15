# Testing script
# append the root project path to the pythonpath so that blockchain.py can be accessed by every adapter

import sys
import os

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from PyInquirer import prompt, print_json, style_from_dict, Token, Separator
from blockchain import Blockchain
import api


bc_choices = [
                {
                    'name': 'Bitcoin',
                    'value': Blockchain.BITCOIN,
                },
                {
                    'name': 'Ethereum',
                    'value': Blockchain.ETHEREUM,
                },
                {
                    'name': 'Stellar',
                    'value': Blockchain.STELLAR,
                },
                {
                    'name': 'EOS',
                    'value': Blockchain.EOS,
                },
                {
                    'name': 'IOTA',
                    'value': Blockchain.IOTA,
                },
                {
                    'name': 'Hyperledger',
                    'value': Blockchain.HYPERLEDGER,
                },
                {
                    'name': 'Multichain',
                    'value': Blockchain.MULTICHAIN,
                },
                {
                    'name': 'Postgres',
                    'value': Blockchain.POSTGRES,
                }
            ]

def askForMethod():
    questions = [
        {
            'type': 'list',
            'message': 'Select action',
            'name': 'action',
            'choices': [
                {
                    'name': 'Store'
                },
                {
                    'name': 'Retrieve'
                },
                {
                    'name': 'Migrate'
                },
            ],
            # 'validate': lambda output: True if (output == "Store") else False
        },

    ]
    try:
        answer = prompt(questions)['action']
        if (answer == 'Store'):
            caseStore()
        elif (answer == 'Retrieve'):
            caseRetrieve()
        elif (answer == 'Migrate'):
            caseMigrate()
    except (KeyboardInterrupt, SystemExit):
        raise
    except (KeyError):
        print('Exiting...')


def caseStore():
    questions = [
        {
            'type': 'list',
            'message': 'Select action',
            'name': 'blockchain',
            'choices': bc_choices,
        },
        {
            'type': 'input',
            'name': 'data',
            'message': 'Please input the data to store',
        },
        {
            'type': 'input',
            'name': 'password',
            'message': 'Please input a password for encryption (press Enter to skip)'
        },
        {
            'type': 'list',
            'name': 'splitting',
            'message': 'Do you wish to enable multiple transactions?',
            'choices': [
                {
                    'name': 'Yes',
                    'value': True
                },
                {
                    'name': 'No',
                    'value': False
                }
            ]
        },
        {
            'type': 'list',
            'name': 'redundancy',
            'message': 'Do you wish to enable redundancy?',
            'choices': [
                {
                    'name': 'Yes',
                    'value': True
                },
                {
                    'name': 'No',
                    'value': False
                },
            ],
        },
    ]
    answer = prompt(questions)
    pw = answer['password'] if answer['password'] != "" else None
    api.store(answer['data'], answer['blockchain'], pw, answer['splitting'], answer['redundancy'])


def caseRetrieve():
    questions = [
        {
            'type': 'input',
            'name': 'hash',
            'message': 'Please input the transaction hash',
        },
        {
            'type': 'input',
            'name': 'password',
            'message': 'Please input a password for decryption if needed (press Enter to skip)'
        }
    ]
    answer = prompt(questions)
    pw = answer['password']
    if pw == "":
        api.retrieve(answer['hash'])
    else:
        api.retrieve(answer['hash'], pw)


def caseMigrate():
    questions = [
        {
            'type': 'input',
            'name': 'hash',
            'message': 'Please input the hash of the transaction connected to the data',
        },
        {
            'type': 'list',
            'name': 'blockchain',
            'message': 'Please select which Blockchain to migrate to',
            'choices': bc_choices,
        },
        {
            'type': 'list',
            'name': 'splitting',
            'message': 'Do you wish to enable multiple transactions?',
            'choices': [
                {
                    'name': 'Yes',
                    'value': True
                },
                {
                    'name': 'No',
                    'value': False
                }
            ]
        }
    ]
    answer = prompt(questions)
    api.migrate(answer['hash'], answer['blockchain'], answer['splitting'])


askForMethod()
