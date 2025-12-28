from DB import get_connection  
from Hashes import aes_decrypt

def get_clients():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, last_name, first_name, patronymic, phone FROM Client")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows

def main():
    clients = get_clients()
    for client in clients:
        client_id, last_name_enc, first_name_enc, patronymic_enc, phone_enc = client
        try:
            last_name = aes_decrypt(last_name_enc)
            first_name = aes_decrypt(first_name_enc)
            patronymic = aes_decrypt(patronymic_enc) if patronymic_enc else ""
            phone = aes_decrypt(phone_enc)
        except Exception as e:
            print(f"Error decrypting client {client_id}: {e}")
            continue
        print(f"Client {client_id}: {last_name} {first_name} {patronymic}, phone: {phone}")

if __name__ == "__main__":
    main()
