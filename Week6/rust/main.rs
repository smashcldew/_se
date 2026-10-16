use std::io::{Read, Write};
use std::net::TcpListener;

fn response(status: &str, body: &str) -> String {
    format!(
        "HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{body}",
        body.len()
    )
}

fn is_prime(value: u64) -> bool {
    if value < 2 { return false; }
    let mut divisor = 2;
    while divisor <= value / divisor {
        if value % divisor == 0 { return false; }
        divisor += if divisor == 2 { 1 } else { 2 };
    }
    true
}

fn main() {
    let listener = TcpListener::bind("0.0.0.0:7000").expect("bind port 7000");
    for stream in listener.incoming().flatten() {
        let mut stream = stream;
        let mut buffer = [0; 2048];
        let size = stream.read(&mut buffer).unwrap_or(0);
        let request = String::from_utf8_lossy(&buffer[..size]);
        let path = request.lines().next().unwrap_or("");
        let output = if path.starts_with("GET /health ") {
            response("200 OK", r#"{"status":"ok","service":"rust"}"#)
        } else if path.starts_with("GET /primes?") || path.starts_with("GET /primes ") {
            let limit = path.split("limit=").nth(1).and_then(|v| v.split_whitespace().next())
                .and_then(|v| v.parse::<u64>().ok()).unwrap_or(100).min(10000);
            let primes: Vec<u64> = (2..=limit).filter(|n| is_prime(*n)).collect();
            let body = format!("{{\"limit\":{limit},\"count\":{},\"primes\":{:?}}}", primes.len(), primes);
            response("200 OK", &body)
        } else {
            response("404 Not Found", r#"{"error":"not found"}"#)
        };
        let _ = stream.write_all(output.as_bytes());
    }
}
