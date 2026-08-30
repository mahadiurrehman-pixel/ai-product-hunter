import { Module, Global } from '@nestjs/common';
import { PrismaService } from './prisma.service';

@Global() // Makes Prisma available to all modules instantly
@Module({
  providers: [PrismaService],
  exports: [PrismaService],
})
export class PrismaModule {}