import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { AppController } from './app.controller';
import { PrismaModule } from './prisma/prisma.module';
import { AuthModule } from './auth/auth.module';
import { EngineModule } from './engine/engine.module';
import { PipelineModule } from './pipeline/pipeline.module';
import { WatchlistModule } from './watchlist/watchlist.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: '../../.env',
    }),
    PrismaModule,
    AuthModule,
    EngineModule,
    PipelineModule,
    WatchlistModule,
  ],
  controllers: [AppController],
})
export class AppModule {}