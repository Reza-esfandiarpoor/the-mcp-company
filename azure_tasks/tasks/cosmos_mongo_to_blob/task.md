I have a cosmosdb mongodb instance on Azure and I want to have all documents that are inserted into mongodb saved to blob storage.
Create a storage account with a blob container named 'docs' inside it.
Then set up a process on Azure that whenever a new document is inserted into mongodb, it creates a corresponding json blob in the above container that contains the content of the newly inserted document from mongodb.
The name of the json blob should be the timestamp of when it is created.
This should happen immediately. The corresponding json blob should appear in storage account immediately after it is inserted into mongodb.
