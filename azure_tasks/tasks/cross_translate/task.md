In your target storage account you will find a container named "sort-me" containing a number of text blobs. Your job is to:
(1) Create five new containers named "orig-en", "orig-fa" and "orig-other", "en-to-fa", "fa-to-en".
(2) For each of the blobs in "sort-me" you must:
    (a) Detect the langauge of the blob.
    (b) If the blob is in English, copy to "orig-en". If it's Farsi, copy to "orig-fa". Otherwise copy it to orig-other.
(3) For each of the blobs in orig-en, translate the file to Farsi and place the translated file, with the same blob name, in en-to-fa. Similarly, translate the files from orig-fa and place the translation in fa-to-en.
