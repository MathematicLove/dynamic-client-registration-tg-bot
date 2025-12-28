package ru.spbstu.telematics.java;

import java.io.File;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;

public class App {
    private static final String URL = "jdbc:mysql://localhost:3306/booking_system?useSSL=false&serverTimezone=UTC";
    private static final String USERNAME = "root";
    private static final String PASSWORD = "Ayzek123321";

    public static void main(String[] args) {
        List<Map<String, Object>> clients = new ArrayList<>();
        List<Map<String, Object>> appointments = new ArrayList<>();
        List<Map<String, Object>> appointmentStatuses = new ArrayList<>();

        Connection connection = null;
        Statement stmt = null;

        try {
            Class.forName("com.mysql.cj.jdbc.Driver");
            connection = DriverManager.getConnection(URL, USERNAME, PASSWORD);
            stmt = connection.createStatement();

            ResultSet rs = stmt.executeQuery("SELECT * FROM Client");
            while (rs.next()) {
                Map<String, Object> row = new HashMap<>();
                row.put("id", rs.getInt("id"));
                row.put("last_name", rs.getString("last_name"));
                row.put("first_name", rs.getString("first_name"));
                row.put("patronymic", rs.getString("patronymic"));
                row.put("phone", rs.getString("phone"));
                clients.add(row);
            }
            rs.close();

            rs = stmt.executeQuery("SELECT * FROM Appointment");
            while (rs.next()) {
                Map<String, Object> row = new HashMap<>();
                row.put("id", rs.getInt("id"));
                row.put("client_id", rs.getInt("client_id"));
                row.put("appointment_date", rs.getDate("appointment_date"));
                row.put("appointment_time", rs.getTime("appointment_time"));
                row.put("full_name", rs.getString("full_name"));
                appointments.add(row);
            }
            rs.close();

            rs = stmt.executeQuery("SELECT * FROM AppointmentStatus");
            while (rs.next()) {
                Map<String, Object> row = new HashMap<>();
                row.put("id", rs.getInt("id"));
                row.put("appointment_id", rs.getInt("appointment_id"));
                row.put("status", rs.getString("status"));
                row.put("client_phone", rs.getString("client_phone"));
                row.put("client_full_name", rs.getString("client_full_name"));
                appointmentStatuses.add(row);
            }
            rs.close();

            Map<String, Object> data = new HashMap<>();
            data.put("clients", clients);
            data.put("appointments", appointments);
            data.put("appointmentStatus", appointmentStatuses);

            ObjectMapper mapper = new ObjectMapper();
            mapper.writerWithDefaultPrettyPrinter().writeValue(new File("booking_system.json"), data);

            System.out.println("JSON file created successfully: booking_system.json");

        } catch (Exception e) {
            e.printStackTrace();
        } finally {
            
            if (stmt != null) {
                try {
                    stmt.close();
                } catch (SQLException se2) {
                    se2.printStackTrace();
                }
            }
            if (connection != null) {
                try {
                    connection.close();
                } catch (SQLException se) {
                    se.printStackTrace();
                }
            }
        }
    }
}
