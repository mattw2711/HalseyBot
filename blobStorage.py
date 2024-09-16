from azure.storage.blob import BlobServiceClient

def initialiseBlobStorage(connection_string):
    
    # Create the BlobServiceClient object
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client('merchbotproducts')

    return container_client