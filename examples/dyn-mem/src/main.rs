use std::time::Duration;

#[cfg(target_os = "hermit")]
use hermit as _;
// extern crate rftrace as _;
// use rftrace_frontend as rftrace;

const M: usize = 1024 * 1024;
const G: usize = 1024 * M;

const INITIAL_ALLOC_SIZE: usize = 4 * G;
const REPEATED_ALLOC_SIZE: usize = 2 * G;
const REPORTING_SIZE: usize = 100 * M;

const SLEEP_DURATION: Duration = Duration::from_secs(2);

fn main() {
	// let events = rftrace::init(1001, true);
	// rftrace::enable();

	{
		println!("<dyn-mem> waiting {SLEEP_DURATION:?} before allocation");
		std::thread::sleep(SLEEP_DURATION);

		println!(
			"<dyn-mem> Allocating large initial buffer ({} MiB)",
			INITIAL_ALLOC_SIZE / M
		);
		alloc_and_fill_buf(INITIAL_ALLOC_SIZE);

		println!("<dyn-mem> waiting {SLEEP_DURATION:?} before deallocation");
		std::thread::sleep(Duration::from_secs(2));
	}

	for _ in 0..3 {
		println!("<dyn-mem> waiting {SLEEP_DURATION:?} before allocation");
		std::thread::sleep(SLEEP_DURATION);

		println!(
			"<dyn-mem> Allocating buffer ({} MiB)",
			REPEATED_ALLOC_SIZE / M
		);
		alloc_and_fill_buf(REPEATED_ALLOC_SIZE);

		println!("<dyn-mem> waiting {SLEEP_DURATION:?} before deallocation");
		std::thread::sleep(SLEEP_DURATION);
	}

	// rftrace::dump_full_uftrace(events, "/tracedir", "dyn-mem").expect("Saving trace failed");
}

fn alloc_and_fill_buf(size: usize) {
	// Talc can't realloc in-place growing to the left, only to the right
	// i.e. reallocating 4GiB with 2GiB already allocated in not quite
	// 8GiB of heap memory is a larger gamble than it would have to be
	let mut buf = Vec::with_capacity(size);

	for i in 0..size {
		buf.push(i as u8);
		if i % REPORTING_SIZE == 0 {
			println!("<dyn-mem> {} MiB", i / M);
		}
	}
}
