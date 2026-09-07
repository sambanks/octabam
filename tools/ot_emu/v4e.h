// The ColdFire V4e instruction set this Musashi is missing, executed from the
// illegal-instruction callback. See v4e.cpp for why that is the extension
// point and how each encoding was verified.
#pragma once

#include <cstdint>

namespace ot
{
	class Machine;

	namespace v4e
	{
		enum class Result { Handled, Unhandled };

		// Decode and run one instruction. On entry the PC is past the opcode
		// word; a handler advances it over its own extension words.
		Result execute(Machine& _m, uint32_t _opcode);
	}
}
