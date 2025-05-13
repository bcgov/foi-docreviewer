package dal

import (
	"database/sql"

	_ "github.com/lib/pq" // PostgreSQL driver
)

type DB struct {
	conn *sql.DB
}

// NewDB initializes a database connection
func NewDB(dataSourceName string) (*DB, error) {
	conn, err := sql.Open("postgres", dataSourceName)
	if err != nil {
		return nil, err
	}

	// Test the connection
	if err := conn.Ping(); err != nil {
		return nil, err
	}

	return &DB{conn: conn}, nil
}

// Close closes the database connection
func (db *DB) Close() error {
	return db.conn.Close()
}
