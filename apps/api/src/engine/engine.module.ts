import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { EngineService } from './engine.service';

@Module({
  imports: [HttpModule, ConfigModule],
  providers: [EngineService],
  exports: [EngineService],
})
export class EngineModule {}