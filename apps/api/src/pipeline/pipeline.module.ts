import { Module } from '@nestjs/common';
import { PipelineController } from './pipeline.controller';
import { EngineModule } from '../engine/engine.module';
import { PrismaModule } from '../prisma/prisma.module';

@Module({
  imports: [EngineModule, PrismaModule],
  controllers: [PipelineController],
})
export class PipelineModule {}