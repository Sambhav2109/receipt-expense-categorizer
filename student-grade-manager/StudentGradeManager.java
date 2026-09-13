import java.io.*;
import java.util.ArrayList;
import java.util.Scanner;

public class StudentGradeManager {
    private static final String FILE_NAME = "students.txt";
    private static final ArrayList<Student> students = new ArrayList<>();
    private static final Scanner scanner = new Scanner(System.in);

    public static void main(String[] args) {
        loadRecords();
        boolean running = true;

        while (running) {
            printMenu();
            String choice = scanner.nextLine().trim();
            switch (choice) {
                case "1" -> addStudent();
                case "2" -> viewStudents();
                case "3" -> searchStudent();
                case "4" -> saveRecords();
                case "5" -> {
                    saveRecords();
                    running = false;
                    System.out.println("Goodbye!");
                }
                default -> System.out.println("Invalid choice. Please enter 1-5.");
            }
        }
        scanner.close();
    }

    private static void printMenu() {
        System.out.println("\n===== STUDENT GRADE MANAGER =====");
        System.out.println("1. Add Student");
        System.out.println("2. View Students");
        System.out.println("3. Search Student");
        System.out.println("4. Save Records");
        System.out.println("5. Exit");
        System.out.print("Enter choice: ");
    }

    private static void addStudent() {
        int roll = readInt("Roll Number: ");
        if (findStudent(roll) != null) {
            System.out.println("A student with this roll number already exists.");
            return;
        }

        System.out.print("Student Name: ");
        String name = scanner.nextLine().trim();
        if (name.isEmpty()) {
            System.out.println("Name cannot be empty.");
            return;
        }

        double javaMarks = readMarks("Java Marks: ");
        double dsaMarks = readMarks("DSA Marks: ");
        double mathsMarks = readMarks("Maths Marks: ");

        Student student = new Student(roll, name, javaMarks, dsaMarks, mathsMarks);
        students.add(student);
        System.out.printf("Added %s — Average: %.2f, Grade: %s%n", name, student.getAverage(), student.getGrade());
    }

    private static void viewStudents() {
        if (students.isEmpty()) {
            System.out.println("No student records found.");
            return;
        }

        System.out.printf("%-8s %-20s %8s %6s%n", "Roll", "Name", "Average", "Grade");
        System.out.println("-----------------------------------------------");
        for (Student student : students) {
            System.out.println(student);
        }
    }

    private static void searchStudent() {
        int roll = readInt("Enter roll number to search: ");
        Student student = findStudent(roll);
        if (student == null) {
            System.out.println("Student not found.");
            return;
        }

        System.out.println("\nStudent Found");
        System.out.println("Name: " + student.getName());
        System.out.println("Roll Number: " + student.getRollNumber());
        System.out.printf("Average: %.2f%n", student.getAverage());
        System.out.println("Grade: " + student.getGrade());
    }

    private static Student findStudent(int roll) {
        for (Student student : students) {
            if (student.getRollNumber() == roll) return student;
        }
        return null;
    }

    private static int readInt(String prompt) {
        while (true) {
            System.out.print(prompt);
            try {
                return Integer.parseInt(scanner.nextLine().trim());
            } catch (NumberFormatException e) {
                System.out.println("Please enter a valid whole number.");
            }
        }
    }

    private static double readMarks(String prompt) {
        while (true) {
            System.out.print(prompt);
            try {
                double marks = Double.parseDouble(scanner.nextLine().trim());
                if (marks >= 0 && marks <= 100) return marks;
            } catch (NumberFormatException ignored) {
                // handled below
            }
            System.out.println("Marks must be a number between 0 and 100.");
        }
    }

    private static void saveRecords() {
        try (PrintWriter writer = new PrintWriter(new FileWriter(FILE_NAME))) {
            for (Student student : students) {
                writer.println(student.toFileString());
            }
            System.out.println("Records saved successfully.");
        } catch (IOException e) {
            System.out.println("Could not save records: " + e.getMessage());
        }
    }

    private static void loadRecords() {
        File file = new File(FILE_NAME);
        if (!file.exists()) return;

        try (BufferedReader reader = new BufferedReader(new FileReader(file))) {
            String line;
            while ((line = reader.readLine()) != null) {
                Student student = Student.fromFileString(line);
                if (student != null && findStudent(student.getRollNumber()) == null) {
                    students.add(student);
                }
            }
        } catch (IOException e) {
            System.out.println("Could not load records: " + e.getMessage());
        }
    }
}
