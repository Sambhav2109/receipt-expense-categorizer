public class Student {
    private final int rollNumber;
    private final String name;
    private final double javaMarks;
    private final double dsaMarks;
    private final double mathsMarks;

    public Student(int rollNumber, String name, double javaMarks, double dsaMarks, double mathsMarks) {
        this.rollNumber = rollNumber;
        this.name = name;
        this.javaMarks = javaMarks;
        this.dsaMarks = dsaMarks;
        this.mathsMarks = mathsMarks;
    }

    public int getRollNumber() {
        return rollNumber;
    }

    public String getName() {
        return name;
    }

    public double getAverage() {
        return (javaMarks + dsaMarks + mathsMarks) / 3.0;
    }

    public String getGrade() {
        double average = getAverage();
        if (average >= 90) return "A+";
        if (average >= 80) return "A";
        if (average >= 70) return "B";
        if (average >= 60) return "C";
        if (average >= 50) return "D";
        return "F";
    }

    public String toFileString() {
        return rollNumber + "|" + name.replace("|", " ") + "|" + javaMarks + "|" + dsaMarks + "|" + mathsMarks;
    }

    public static Student fromFileString(String line) {
        String[] parts = line.split("\\|", -1);
        if (parts.length != 5) return null;
        try {
            return new Student(
                Integer.parseInt(parts[0]),
                parts[1],
                Double.parseDouble(parts[2]),
                Double.parseDouble(parts[3]),
                Double.parseDouble(parts[4])
            );
        } catch (NumberFormatException e) {
            return null;
        }
    }

    @Override
    public String toString() {
        return String.format("%-8d %-20s %8.2f %6s", rollNumber, name, getAverage(), getGrade());
    }
}
