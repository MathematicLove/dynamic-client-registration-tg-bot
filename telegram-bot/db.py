import mysql.connector
from mysql.connector import Error
from datetime import datetime

config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Ayzek123321',
    'database': 'booking_system'
}

def get_connection():
    """Возвращает подключение к базе данных."""
    try:
        connection = mysql.connector.connect(**config)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Connection error: {e}")
        raise

def insert_log(log_text):
    """Записывает сообщение об ошибке в таблицу Logs."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        log_date = datetime.now().date()
        query = "INSERT INTO Logs (log_date, log_text) VALUES (%s, %s)"
        cursor.execute(query, (log_date, log_text))
        conn.commit()
        cursor.close()
        conn.close()
    except Error as e:
        print(f"Failed to insert log: {e}")

def insert_client(last_name, first_name, patronymic, phone):
    """Вставляет нового клиента в таблицу Client. Возвращает client_id."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO Client (last_name, first_name, patronymic, phone)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (last_name, first_name, patronymic, phone))
        conn.commit()
        client_id = cursor.lastrowid
        print(f"insert_client: client_id = {client_id}")   
        cursor.close()
        conn.close()
        return client_id
    except Error as e:
        insert_log(f"Error inserting client: {e}")
        raise

def insert_appointment(client_id, appointment_date, appointment_time, full_name):
    """
    Вставляет новую запись в таблицу Appointment.
    Возвращает appointment_id.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO Appointment (client_id, appointment_date, appointment_time, full_name)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (client_id, appointment_date, appointment_time, full_name))
        conn.commit()
        appointment_id = cursor.lastrowid
        print(f"insert_appointment: appointment_id = {appointment_id}")  
        cursor.close()
        conn.close()
        return appointment_id
    except Error as e:
        insert_log(f"Error inserting appointment: {e}")
        raise

def update_appointment(appointment_id, appointment_date, appointment_time, full_name):
    """Обновляет запись в таблице Appointment."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            UPDATE Appointment
            SET appointment_date = %s, appointment_time = %s, full_name = %s
            WHERE id = %s
        """
        cursor.execute(query, (appointment_date, appointment_time, full_name, appointment_id))
        conn.commit()
        print(f"update_appointment: updated appointment_id = {appointment_id}")  
        cursor.close()
        conn.close()
    except Error as e:
        insert_log(f"Error updating appointment {appointment_id}: {e}")
        raise

def insert_status(appointment_id, status, client_phone, client_full_name):
    """
    Вставляет статус записи в таблицу AppointmentStatus.
    Статус:
      - "finished" – если клиент нажал "Уже здесь!"
      - "cancelled" – если клиент нажал "Нет, не приду"
      - "pending" – если клиент нажал "Да, приду" или "Да, но опоздаю"
    Возвращает status_id.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            INSERT INTO AppointmentStatus (appointment_id, status, client_phone, client_full_name)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(query, (appointment_id, status, client_phone, client_full_name))
        conn.commit()
        status_id = cursor.lastrowid
        print(f"insert_status: status_id = {status_id}")   
        cursor.close()
        conn.close()
        return status_id
    except Error as e:
        insert_log(f"Error inserting appointment status for appointment {appointment_id}: {e}")
        raise

def update_status(appointment_id, status, client_phone, client_full_name):
    """Обновляет статус записи в таблице AppointmentStatus."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        query = """
            UPDATE AppointmentStatus
            SET status = %s, client_phone = %s, client_full_name = %s
            WHERE appointment_id = %s
        """
        cursor.execute(query, (status, client_phone, client_full_name, appointment_id))
        conn.commit()
        print(f"update_status: updated appointment_id = {appointment_id}")   
        cursor.close()
        conn.close()
    except Error as e:
        insert_log(f"Error updating status for appointment {appointment_id}: {e}")
        raise

if __name__ == "__main__":
    try:
        client_id = insert_client("Иванов", "Иван", "Иванович", "+7 999 999 99 99")
        print(f"Inserted client with id: {client_id}")
        appointment_id = insert_appointment(client_id, "2025-03-10", "14:00", "Иванов Иван Иванович")
        print(f"Inserted appointment with id: {appointment_id}")
        status_id = insert_status(appointment_id, "pending", "+7 999 999 99 99", "Иванов Иван Иванович")
        print(f"Inserted appointment status with id: {status_id}")
    except Exception as ex:
        print("Exception:", ex)
