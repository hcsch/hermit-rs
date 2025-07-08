use sysinfo::System;

fn main() {
	println!("Applying artificial memory pressure...");

	let mut sys = System::new();
	sys.refresh_memory();

	let mem_available = sys.available_memory();

	println!(
		"Allocating and filling buffer of {} MiB...",
		mem_available / (1024 * 1024)
	);

	#[expect(
		unused_variables,
		reason = "we use this buffer to fill up memory, not for its contents"
	)]
	let buf = vec![
		!0u8;
		sys.available_memory()
			.try_into()
			.expect("We only support 64-bit architectures")
	];

	println!("Done!");
}
