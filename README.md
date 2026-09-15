# Bifröst: a Modular Blockchain Interoperability API - Version 2

<p align="center">
<img src="img/bifrost-logo.png" width="300x"></img>
</p>

The blockchain (BC) world is rapidly becoming a universe of several ledgers designed for a specific purpose, holding data previously stored (i.e., siloed) in centralized databases. The use of different BCs for the same purpose could hamper the frictionless exchange of data or value. On one hand, it is natural that there are competing implementations exploring the benefits of BC. On the other hand, the problem of siloed data re-emerges, with respect to isolated chains. In this regard, BC interoperability is necessary to connect different BCs, exchanging information and assets. Moreover, to foster BC employment, developers must be able to interact with such different BCs without knowing the details of each implementation. This paper presents a novel solution, called Bifröst, to store and retrieve data on different BCs. Bifröst employs a notary scheme, which allows for connectivity to different BCs. The presented prototype is highly modular and currently implements seven adapters to popular BC implementations, including Bitcoin, Ethereum, and Stellar. The developed prototype was evaluated concerning performance, security, and data size to verify the feasibility of such an implementation and assess design decisions taken during its development.

## Usage

```python
from api import store, retrieve, migrate, Blockchain

tx_hash = store('Some Data', Blockchain.STELLAR)    

data = retrieve('[Transaction_Hash]')    

tx_hash = migrate('[Transaction_Hash]', Blockchain.ETHEREUM)
```

Or use the CLI:
```python
source venv/bin/activate

python3 cli.py
```




## Setup

Python 3.7.1 (also tested with 3.8.3) was used for this project. It was tested on MacOS. 

Previous versions of the project were also tested on Ubuntu 18, hence the Linux specific installation instructions. These have not been re-tested but should still be valid.

### Install Docker
(Linux) Follow [this](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-on-ubuntu-18-04) or [this](https://docs.docker.com/install/linux/docker-ce/ubuntu/#install-docker-ce-1) manual and then do `sudo apt-get install docker-compose`    

(Mac) Install from https://docs.docker.com/docker-for-mac/install/

### Setup virtual environment (venv)
(Linux Only) Install venv:    
`sudo apt-get install python3-venv`    
Create environment:    
`python3 -m venv myNewVenv`    
Activate environment:    
`source myNewVenv/bin/activate`    
The python version of the environment will be the one with which the environment is created.    
       
Don't forget to add the name of your new environment in the `.gitignore` under the `# Environments` header to prevent installed packages from being tracked by git.

### Install dependencies

#### Preparation
First, upgrade pip: `pip install --upgrade pip`     
(Linux only)`sudo apt-get install build-essential libssl-dev libffi-dev python3-dev`

*Upgrade pip on <3.6:*    
(Mac only) Use this command if upgrading upgrading pip fails due to SSL cert error:    
`curl https://bootstrap.pypa.io/get-pip.py | python`

#### Important Notice
Note that there are two files that carry information about the dependencies and their respective versions, `requirements.txt` and `requirements_unresolved.txt`.

The normal `requirements.txt` has specific version information for each dependency, as resolved by pip. 
The unresolved requirements file has no specific version set for packages that caused issues when performing the initial setup for the development.

Thus use `requirements_unresolved.txt` in case you get incompatible sub-dependency versions in the next step with the normal `requirements.txt`. This will let pip resolve the versioning on its own.

#### Install/Export Dependencies  
Import/Install depenencies: `myNewVenv/bin/pip install -r requirements.txt`    
Export: `myNewVenv/bin/pip freeze > requirements.txt`    

(In case of errors, read the Important Notice under the previous header.)

### Database Setup
(Mac Only) Install sqlite: `brew install sqlite3`    
Then import and setup the DB:    
```
import db.database
db.database.setup()
```

Calling the `setup` function of the [`database`](database.py) module will:

1. drop `credentials` and `transactions` tables if they already exist
2. create tables for storing `credentials` and `transactions`
3. seed the `credentials` table with credentials 
4. seed the `transactions` table with input transactions

Seed values are read from the [`config`](config.py) module.

### Blockchain Setup

See descriptions in [SETUP.md](SETUP.md) for instruction to setup the local nodes.
