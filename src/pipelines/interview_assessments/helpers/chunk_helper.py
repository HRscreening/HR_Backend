# helper function to create chunks with overlap
def chunk_with_overlap(sentences, chunk_size=5, overlap=2):
    chunks = []
    
    i = 0
    while i < len(sentences):
        chunk = sentences[i:i + chunk_size]

        text = "\n".join([
            f'{s["speaker"]}: {s["text"]}'
            for s in chunk
        ])

        chunks.append(text)

        i += (chunk_size - overlap)  # move forward with overlap

    return chunks
