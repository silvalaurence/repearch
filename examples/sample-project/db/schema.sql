CREATE TABLE residents (
  id INT PRIMARY KEY,
  full_name VARCHAR(100) NOT NULL,
  address TEXT
);
CREATE TABLE staff (
  id INT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL
);
CREATE TABLE tickets (
  id INT PRIMARY KEY,
  resident_id INT NOT NULL,
  called_by INT,
  status VARCHAR(20),
  created_at TIMESTAMP,
  FOREIGN KEY (resident_id) REFERENCES residents(id),
  FOREIGN KEY (called_by) REFERENCES staff(id)
);
